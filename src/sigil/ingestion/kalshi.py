"""Kalshi data source.

Targets the current Kalshi Elections API at ``api.elections.kalshi.com``.
Both REST and WS require RSA-PSS signed headers; provide
``config.KALSHI_KEY_ID`` + ``KALSHI_PRIVATE_KEY_PATH`` (or _PEM). See
``sigil/ingestion/kalshi_auth.py``.

Schema notes (post-migration):
- REST `/markets` returns prices as decimal strings in `*_dollars`
  fields (e.g. ``"0.4200"``) plus integer cents in some legacy fields.
  We parse dollars; the WS ladder is in cents (integer).
- ``status`` values now include ``active|finalized|...``; only
  ``active`` corresponds to our internal ``open``.
- ``ticker`` remains the external_id; ``event_ticker`` groups markets.
- ``category`` has moved off ``/markets`` onto ``/events``; we leave
  ``taxonomy_l1`` as ``"general"`` here and let an enrichment step
  fill it from ``/events/{event_ticker}`` later.
"""
from __future__ import annotations

import json
import logging
from typing import Any, AsyncIterator, List, Optional

import httpx
import pandas as pd
import websockets

from sigil.config import config
from sigil.ingestion.base import DataSource
from sigil.ingestion.kalshi_auth import (
    KalshiAuthConfig,
    KalshiAuthError,
    auth_headers,
)


logger = logging.getLogger(__name__)


_DEFAULT_REST = "https://api.elections.kalshi.com/trade-api/v2"
_DEFAULT_WS = "wss://api.elections.kalshi.com/trade-api/ws/v2"


# Kalshi's /events/{ticker} returns the official category but is auth-gated.
# This map covers the dominant series prefixes seen in /markets responses.
# Source: hand-mapped from observed event_tickers in production DB. Replace
# with a real lookup when Kalshi creds are available.
_KALSHI_PREFIX_CATEGORY: tuple[tuple[str, str], ...] = (
    # Sports
    ("KXNBA", "sports"),
    ("KXNFL", "sports"),
    ("KXMLB", "sports"),
    ("KXNHL", "sports"),
    ("KXEPL", "sports"),
    ("KXLALIGA", "sports"),
    ("KXBUNDES", "sports"),
    ("KXSERIEA", "sports"),
    ("KXLIGUE1", "sports"),
    ("KXUFC", "sports"),
    ("KXBOX", "sports"),
    ("KXTENNIS", "sports"),
    ("KXATP", "sports"),
    ("KXWTA", "sports"),
    ("KXGOLF", "sports"),
    ("KXPGA", "sports"),
    ("KXMASTERS", "sports"),
    ("KXCFB", "sports"),
    ("KXNCAAB", "sports"),
    ("KXNCAAF", "sports"),
    ("KXOLYMPIC", "sports"),
    ("KXFORMULA", "sports"),
    ("KXF1", "sports"),
    ("KXNASCAR", "sports"),
    ("KXCRICKET", "sports"),
    ("KXIPL", "sports"),
    # Economics
    ("KXFED", "economics"),
    ("KXCPI", "economics"),
    ("KXGDP", "economics"),
    ("KXJOBS", "economics"),
    ("KXNFP", "economics"),
    ("KXUNRATE", "economics"),
    ("KXRECESS", "economics"),
    ("KXTREASURY", "economics"),
    # Crypto
    ("KXBTC", "crypto"),
    ("KXETH", "crypto"),
    ("KXSOL", "crypto"),
    ("KXCRYPTO", "crypto"),
    # Politics / elections
    ("KXPRES", "politics"),
    ("KXELECTION", "politics"),
    ("KXGOV", "politics"),
    ("KXSENATE", "politics"),
    ("KXHOUSE", "politics"),
    ("KXCONGRESS", "politics"),
    # Climate / weather
    ("KXTEMP", "climate"),
    ("KXHURRICANE", "climate"),
    ("KXHIGHNY", "climate"),
    ("KXHIGH", "climate"),
    # Entertainment / culture
    ("KXOSCAR", "entertainment"),
    ("KXEMMY", "entertainment"),
    ("KXGRAMMY", "entertainment"),
    ("KXBOXOFF", "entertainment"),
    ("KXSPOTIFY", "entertainment"),
    # Tech
    ("KXAI", "tech"),
    ("KXOPENAI", "tech"),
    ("KXMUSK", "tech"),
)


def _infer_category_from_ticker(event_ticker: Optional[str], ticker: Optional[str]) -> str:
    """Map a Kalshi ticker (or event_ticker) to a Sigil taxonomy_l1.

    Match order: longest prefix wins so 'KXNCAAF' beats a hypothetical
    'KX' fallback. Falls back to 'general' when nothing matches.
    """
    candidate = (event_ticker or ticker or "").upper()
    if not candidate:
        return "general"
    best_prefix = ""
    best_category = "general"
    for prefix, category in _KALSHI_PREFIX_CATEGORY:
        if candidate.startswith(prefix) and len(prefix) > len(best_prefix):
            best_prefix = prefix
            best_category = category
    return best_category


def _resolve_auth() -> KalshiAuthConfig:
    return KalshiAuthConfig.from_config(
        key_id=config.KALSHI_KEY_ID,
        private_key_pem=config.KALSHI_PRIVATE_KEY_PEM,
        private_key_path=config.KALSHI_PRIVATE_KEY_PATH,
    )


def _to_float_or_none(v: Any) -> Optional[float]:
    if v is None or v == "":
        return None
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


class KalshiDataSource(DataSource):
    name: str = "kalshi_markets"
    refresh_interval: int = 60

    def __init__(
        self,
        base_url: str = _DEFAULT_REST,
        ws_url: str = _DEFAULT_WS,
        *,
        auth: Optional[KalshiAuthConfig] = None,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.ws_url = ws_url
        # Path used in the signature must be absolute; we extract once.
        # https://api.elections.kalshi.com/trade-api/v2 -> /trade-api/v2
        self._path_prefix = httpx.URL(self.base_url).path.rstrip("/")
        self._auth = auth
        self.client = httpx.AsyncClient(base_url=self.base_url, timeout=20.0)

    def _resolve_auth(self) -> KalshiAuthConfig:
        if self._auth is None:
            self._auth = _resolve_auth()
        return self._auth

    def _signed_headers(self, *, method: str, sub_path: str) -> dict:
        """``sub_path`` is the path beneath ``base_url`` (must start with ``/``)."""
        full_path = f"{self._path_prefix}{sub_path}"
        return auth_headers(self._resolve_auth(), method=method, path=full_path)

    async def fetch(self, *, status: str = "open", limit: int = 100) -> List[dict]:
        """Fetch one page of markets matching ``status`` (default ``open``).

        We don't paginate by default — for live ingestion the operator
        chooses an event-ticker filter or accepts the first page.
        """
        try:
            headers = self._signed_headers(method="GET", sub_path="/markets")
        except KalshiAuthError as exc:
            logger.warning("Kalshi auth not configured: %s", exc)
            return []
        try:
            r = await self.client.get(
                "/markets",
                params={"status": status, "limit": limit},
                headers=headers,
            )
        except Exception as exc:
            logger.warning("Kalshi REST /markets failed: %s", exc)
            return []
        if r.status_code != 200:
            logger.warning(
                "Kalshi REST /markets HTTP %s: %s", r.status_code, r.text[:200]
            )
            return []
        body = r.json()
        return body.get("markets", []) if isinstance(body, dict) else []

    def normalize(self, raw_data: List[dict]) -> pd.DataFrame:
        """Convert Kalshi market records to Sigil's Market schema."""
        rows = []
        for m in raw_data:
            ticker = m.get("ticker")
            if not ticker:
                continue
            kalshi_status = (m.get("status") or "").lower()
            internal_status = "open" if kalshi_status == "active" else kalshi_status or "unknown"
            rows.append({
                "external_id": ticker,
                "platform": "kalshi",
                "title": m.get("title") or m.get("yes_sub_title") or ticker,
                # Kalshi /markets no longer carries category — derive from
                # the event_ticker prefix until /events/{ticker} auth lands.
                "taxonomy_l1": _infer_category_from_ticker(
                    m.get("event_ticker"), ticker
                ),
                "market_type": m.get("market_type") or "binary",
                "status": internal_status,
                "resolution_date": m.get("expiration_time")
                                    or m.get("close_time")
                                    or m.get("latest_expiration_time"),
            })
        return pd.DataFrame(rows)

    def validate(self, df: pd.DataFrame) -> bool:
        required = {"external_id", "platform", "title", "taxonomy_l1"}
        return required.issubset(df.columns) and not df.empty

    async def stream_prices(self, market_tickers: List[str]) -> AsyncIterator[dict]:
        """Stream WS orderbook_delta ticks for ``market_tickers``.

        Auth headers are computed against the WS path. The WS ladder is
        in integer cents; we convert to dollars in the yielded tick.
        """
        if not market_tickers:
            return
        try:
            ws_path = httpx.URL(self.ws_url).path or "/trade-api/ws/v2"
            headers = auth_headers(self._resolve_auth(), method="GET", path=ws_path)
        except KalshiAuthError as exc:
            logger.warning("Kalshi WS auth not configured: %s", exc)
            return

        async with websockets.connect(
            self.ws_url,
            additional_headers=list(headers.items()),
            open_timeout=15,
        ) as ws:
            await ws.send(json.dumps({
                "id": 1,
                "cmd": "subscribe",
                "params": {
                    "channels": ["orderbook_delta"],
                    "market_tickers": market_tickers,
                },
            }))
            async for message in ws:
                try:
                    data = json.loads(message)
                except Exception:
                    continue
                if data.get("type") != "orderbook_delta":
                    continue
                msg = data.get("msg") or {}
                ticker = msg.get("market_ticker")
                if not ticker:
                    continue
                bids = msg.get("bids") or []
                asks = msg.get("asks") or []
                # Kalshi ladder entries are [price_cents, size] integers.
                best_bid = (float(bids[0][0]) / 100.0) if bids and bids[0] else None
                best_ask = (float(asks[0][0]) / 100.0) if asks and asks[0] else None
                yield {
                    "market_id": ticker,
                    "platform": "kalshi",
                    "bid": best_bid,
                    "ask": best_ask,
                    "last_price": best_bid,
                    "time": pd.Timestamp.now("UTC"),
                    "volume_24h": None,
                    "open_interest": None,
                    "source": "exchange_ws",
                    "bids": bids,
                    "asks": asks,
                }
