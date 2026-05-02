"""Polymarket data source (read-only — decision 1C).

Targets the Polymarket Gamma API (used by polymarket.com itself) for
metadata and the CLOB WebSocket for live order-book updates.

Schema notes:
- Gamma `/markets?active=true&closed=false` returns camelCase fields:
  ``conditionId``, ``clobTokenIds`` (JSON-stringified array of token id
  strings), ``outcomes`` (JSON-stringified array, position-aligned with
  ``clobTokenIds``), ``endDate``, ``volume``, ``liquidity``.
- The CLOB-side ``/markets`` endpoint returns *historical* archives
  first; do not use it.
- WebSocket emits two event shapes:
    ``book`` — full snapshot. Fields: ``asset_id``, ``market``,
        ``bids``/``asks`` (lists of ``{price, size}`` strings),
        ``last_trade_price``, ``timestamp``, ``hash``.
    ``price_change`` — list of deltas. Each entry includes ``best_bid``
        and ``best_ask`` already, so no local book reconstruction is
        needed.
- We emit one tick per YES-side update only. ``outcomes[0]`` is the YES
  outcome by Polymarket convention; ``clobTokenIds[0]`` is therefore
  the YES token id. NO-side updates are ignored.
"""
from __future__ import annotations

import json
import logging
from typing import Any, AsyncIterator, Dict, List, Optional

import httpx
import pandas as pd
import websockets

from sigil.ingestion.base import DataSource


logger = logging.getLogger(__name__)


_DEFAULT_REST = "https://gamma-api.polymarket.com"
_DEFAULT_WS = "wss://ws-subscriptions-clob.polymarket.com/ws/market"


def _to_float_or_none(v: Any) -> Optional[float]:
    if v is None or v == "":
        return None
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def _parse_json_array(raw: Any) -> List[Any]:
    """Polymarket sometimes returns lists as JSON-stringified arrays."""
    if isinstance(raw, list):
        return raw
    if isinstance(raw, str) and raw:
        try:
            v = json.loads(raw)
            return v if isinstance(v, list) else []
        except Exception:
            return []
    return []


class PolymarketDataSource(DataSource):
    """Read-only Polymarket adapter (no order placement — decision 1C)."""

    name: str = "polymarket_clob"
    refresh_interval: int = 60

    def __init__(
        self,
        base_url: str = _DEFAULT_REST,
        ws_url: str = _DEFAULT_WS,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.ws_url = ws_url
        self.client = httpx.AsyncClient(base_url=self.base_url, timeout=20.0)
        # asset_id -> condition_id, populated by fetch().
        # Used to filter WS messages to YES-side and look up the market.
        self._yes_token_to_market: Dict[str, str] = {}

    async def fetch(self, *, limit: int = 100) -> List[dict]:
        """Fetch live, order-book-enabled markets sorted by volume desc.

        Side-effect: rebuilds the internal ``yes_token -> market`` map so
        :meth:`stream_prices` can filter and look up.
        """
        try:
            r = await self.client.get(
                "/markets",
                params={
                    "active": "true",
                    "closed": "false",
                    "limit": str(limit),
                    "order": "volume",
                    "ascending": "false",
                },
            )
        except Exception as exc:
            logger.warning("Polymarket gamma fetch failed: %s", exc)
            return []
        if r.status_code != 200:
            logger.warning(
                "Polymarket gamma HTTP %s: %s", r.status_code, r.text[:200]
            )
            return []
        body = r.json()
        if not isinstance(body, list):
            return []

        # Rebuild the YES-token -> condition_id map.
        new_map: Dict[str, str] = {}
        for m in body:
            cid = m.get("conditionId") or m.get("condition_id")
            if not cid:
                continue
            tokens = _parse_json_array(m.get("clobTokenIds"))
            outcomes = _parse_json_array(m.get("outcomes"))
            yes_token: Optional[str] = None
            # Prefer outcome-aligned: position of "Yes"/"YES" in outcomes
            for i, label in enumerate(outcomes):
                if isinstance(label, str) and label.strip().lower() == "yes":
                    if i < len(tokens) and isinstance(tokens[i], str):
                        yes_token = tokens[i]
                    break
            # Fall back to position 0 if outcomes is empty / non-standard.
            if yes_token is None and tokens and isinstance(tokens[0], str):
                yes_token = tokens[0]
            if yes_token:
                new_map[yes_token] = cid
        self._yes_token_to_market = new_map
        return body

    def normalize(self, raw_data: List[dict]) -> pd.DataFrame:
        rows = []
        for m in raw_data:
            cid = m.get("conditionId") or m.get("condition_id")
            if not cid:
                continue
            description = m.get("description")
            if isinstance(description, str):
                description = description.strip() or None
            else:
                description = None
            archived_raw = m.get("archived")
            archived = bool(archived_raw) if archived_raw is not None else False
            rows.append({
                "external_id": cid,
                "platform": "polymarket",
                "title": m.get("question", "Unknown"),
                "taxonomy_l1": (m.get("category") or "general").lower(),
                "market_type": "binary",
                "status": "open",
                "resolution_date": m.get("endDate") or m.get("end_date_iso"),
                "description": description,
                "archived": archived,
            })
        return pd.DataFrame(rows)

    def validate(self, df: pd.DataFrame) -> bool:
        return "external_id" in df.columns and not df.empty

    @property
    def yes_token_ids(self) -> List[str]:
        """All YES-side token ids known after the most recent ``fetch()``."""
        return list(self._yes_token_to_market.keys())

    async def stream_prices(self, market_ids: List[str]) -> AsyncIterator[dict]:
        """Stream YES-side ticks for the supplied token ids.

        Despite the name ``market_ids``, callers should pass *token ids*
        (typically ``self.yes_token_ids`` after a ``fetch()``). The yield
        shape's ``market_id`` field is the resolved ``condition_id`` so
        downstream processors can map to ``Market.external_id`` directly.
        """
        if not market_ids:
            return

        async with websockets.connect(self.ws_url, open_timeout=15) as ws:
            await ws.send(json.dumps({
                "assets_ids": list(market_ids),
                "type": "market",
            }))
            async for raw in ws:
                try:
                    data = json.loads(raw)
                except Exception:
                    continue
                # `book` events arrive in lists; `price_change` events as bare dicts.
                events = data if isinstance(data, list) else [data]
                for event in events:
                    if not isinstance(event, dict):
                        continue
                    et = event.get("event_type")
                    if et == "book":
                        async for tick in self._yield_book(event):
                            yield tick
                    elif et == "price_change":
                        async for tick in self._yield_price_changes(event):
                            yield tick

    async def _yield_book(self, event: dict) -> AsyncIterator[dict]:
        asset_id = event.get("asset_id")
        cid = self._yes_token_to_market.get(asset_id) if asset_id else None
        if cid is None:
            return  # not the YES side, or unknown asset
        bids = event.get("bids") or []
        asks = event.get("asks") or []
        # Lists of {"price": str, "size": str}; best = max-bid / min-ask.
        bid_prices = [_to_float_or_none(b.get("price")) for b in bids if isinstance(b, dict)]
        ask_prices = [_to_float_or_none(a.get("price")) for a in asks if isinstance(a, dict)]
        bid_prices = [p for p in bid_prices if p is not None]
        ask_prices = [p for p in ask_prices if p is not None]
        best_bid = max(bid_prices) if bid_prices else None
        best_ask = min(ask_prices) if ask_prices else None
        last_price = _to_float_or_none(event.get("last_trade_price"))
        yield {
            "market_id": cid,
            "platform": "polymarket",
            "bid": best_bid,
            "ask": best_ask,
            "last_price": last_price if last_price is not None else best_bid,
            "time": pd.Timestamp.now("UTC"),
            "volume_24h": None,
            "open_interest": None,
            "source": "exchange_ws",
            "bids": bids,
            "asks": asks,
        }

    async def _yield_price_changes(self, event: dict) -> AsyncIterator[dict]:
        for change in event.get("price_changes") or []:
            if not isinstance(change, dict):
                continue
            asset_id = change.get("asset_id")
            cid = self._yes_token_to_market.get(asset_id) if asset_id else None
            if cid is None:
                continue
            best_bid = _to_float_or_none(change.get("best_bid"))
            best_ask = _to_float_or_none(change.get("best_ask"))
            yield {
                "market_id": cid,
                "platform": "polymarket",
                "bid": best_bid,
                "ask": best_ask,
                "last_price": best_bid,
                "time": pd.Timestamp.now("UTC"),
                "volume_24h": None,
                "open_interest": None,
                "source": "exchange_ws",
                # No depth in price_change events — only the changed level.
                "bids": [],
                "asks": [],
            }
