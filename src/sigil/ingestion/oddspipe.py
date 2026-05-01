"""OddsPipe data source — third-party aggregator for Kalshi + Polymarket.

Useful when direct Kalshi creds aren't available (the Kalshi public API
requires RSA-PSS signed auth; OddsPipe wraps both platforms behind a
single ``X-API-Key`` header). REST only — no WebSocket. The
``stream_prices`` coroutine is therefore a polling loop, defaulting to
``config.ODDSPIPE_POLL_SECONDS`` (5 minutes per decision 4A) between
fetches.

API shape (verified against the live spec at
``https://oddspipe.com/openapi.json``):

    GET /v1/markets?platform=<kalshi|polymarket>&limit=<N>
    -> { "total": N, "limit": N, "offset": N, "items": [
            {
              "id": int,                       # OddsPipe internal id
              "title": str,
              "category": str | null,
              "status": "active" | ...,
              "source": {
                "platform": "kalshi" | "polymarket",
                "platform_market_id": str,     # <- the canonical external_id
                "url": str,
                "latest_price": {
                  "yes_price": float,
                  "no_price": float,
                  "volume_usd": float,
                  "snapshot_at": str
                }
              }
            }
         ]
       }

Only YES-side prices are emitted (binary markets — decision 1C). Ticks
land in ``MarketPrice`` with ``source = "oddspipe"`` so they coexist
with the direct exchange WS feed (``source = "exchange_ws"``).
"""
from __future__ import annotations

import asyncio
import logging
from typing import Any, AsyncIterator, Iterable, List, Optional

import httpx
import pandas as pd

from sigil.ingestion.base import DataSource


logger = logging.getLogger(__name__)


_DEFAULT_BASE_URL = "https://oddspipe.com"


class OddsPipeAuthError(RuntimeError):
    """Raised when ``ODDSPIPE_API_KEY`` is missing."""


class OddsPipeDataSource(DataSource):
    name: str = "oddspipe"
    refresh_interval: int = 300  # decision 4A — 5-min freshness

    def __init__(
        self,
        api_key: Optional[str],
        *,
        base_url: str = _DEFAULT_BASE_URL,
        platforms: Iterable[str] = ("kalshi", "polymarket"),
        markets_per_platform: int = 100,
    ) -> None:
        self.api_key = api_key
        self.base_url = base_url.rstrip("/")
        self.platforms = tuple(platforms)
        self.markets_per_platform = int(markets_per_platform)
        self.client = httpx.AsyncClient(
            base_url=self.base_url,
            timeout=30.0,
            headers={"X-API-Key": api_key} if api_key else {},
        )

    def _require_key(self) -> None:
        if not self.api_key:
            raise OddsPipeAuthError(
                "ODDSPIPE_API_KEY missing. Set in secrets.local.yaml or sops."
            )

    async def fetch(self) -> List[dict]:
        """One page of markets per platform, merged.

        Skips per-platform errors so one platform 5xx doesn't kill the
        whole cycle. Returns the raw item dicts; ``normalize`` flattens
        for the runner.
        """
        self._require_key()
        items: List[dict] = []
        for platform in self.platforms:
            try:
                r = await self.client.get(
                    "/v1/markets",
                    params={
                        "platform": platform,
                        "limit": str(self.markets_per_platform),
                    },
                )
            except Exception as exc:
                logger.warning("OddsPipe /v1/markets %s failed: %s", platform, exc)
                continue
            if r.status_code != 200:
                logger.warning(
                    "OddsPipe /v1/markets %s HTTP %s: %s",
                    platform, r.status_code, r.text[:200],
                )
                continue
            body = r.json()
            for it in (body.get("items") or []):
                items.append(it)
        return items

    def normalize(self, raw_data: List[dict]) -> pd.DataFrame:
        rows = []
        for it in raw_data:
            src = it.get("source") or {}
            ext_id = src.get("platform_market_id")
            platform = src.get("platform")
            if not ext_id or not platform:
                continue
            status_raw = (it.get("status") or "").lower()
            status = "open" if status_raw == "active" else (status_raw or "unknown")
            rows.append({
                "external_id": ext_id,
                "platform": platform,
                "title": it.get("title") or ext_id,
                "taxonomy_l1": (it.get("category") or "general").lower() if it.get("category") else "general",
                "market_type": "binary",
                "status": status,
                "resolution_date": None,  # not exposed by /v1/markets
            })
        return pd.DataFrame(rows)

    def validate(self, df: pd.DataFrame) -> bool:
        required = {"external_id", "platform", "title"}
        return required.issubset(df.columns) and not df.empty

    @staticmethod
    def _emit_tick(item: dict) -> Optional[dict]:
        src = item.get("source") or {}
        ext_id = src.get("platform_market_id")
        platform = src.get("platform")
        if not ext_id or not platform:
            return None
        lp = src.get("latest_price") or {}
        yes = lp.get("yes_price")
        if yes is None:
            return None
        try:
            yes_f = float(yes)
        except (TypeError, ValueError):
            return None
        vol = lp.get("volume_usd")
        try:
            vol_f = float(vol) if vol is not None else None
        except (TypeError, ValueError):
            vol_f = None
        return {
            "market_id": ext_id,
            "platform": platform,
            "bid": yes_f,
            "ask": yes_f,
            "last_price": yes_f,
            "time": pd.Timestamp.now("UTC"),
            "volume_24h": vol_f,
            "open_interest": None,
            "source": "oddspipe",
            "bids": [],
            "asks": [],
        }

    async def stream_prices(
        self,
        market_ids: List[str],
        *,
        poll_interval: Optional[int] = None,
    ) -> AsyncIterator[dict]:
        """Polling loop. Yields one tick per known market per cycle.

        ``market_ids`` is unused — OddsPipe returns all known markets per
        platform on each fetch and we emit every tick whose
        ``platform_market_id`` resolves. The runner's
        ``MarketIdResolver`` filters by upserted markets at write time.
        """
        period = int(poll_interval if poll_interval is not None else self.refresh_interval)
        while True:
            try:
                raw = await self.fetch()
            except OddsPipeAuthError as exc:
                logger.warning("OddsPipe auth missing: %s", exc)
                return
            except Exception as exc:
                logger.warning("OddsPipe fetch error: %s", exc)
                raw = []
            for item in raw:
                tick = self._emit_tick(item)
                if tick is not None:
                    yield tick
            await asyncio.sleep(period)
