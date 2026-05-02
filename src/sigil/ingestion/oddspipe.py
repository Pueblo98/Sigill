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
from dataclasses import dataclass
from typing import Any, AsyncIterator, Dict, Iterable, List, Optional, Tuple

import httpx
import pandas as pd

from sigil.ingestion.base import DataSource


@dataclass(frozen=True)
class SpreadSide:
    """One side of a cross-platform spread match."""
    platform: str
    internal_id: int             # OddsPipe-internal numeric id
    external_id: Optional[str]   # platform_market_id, if known via fetch()
    yes_price: float
    no_price: float
    volume_usd: float
    title: str


@dataclass(frozen=True)
class SpreadMatch:
    """A pair of markets that OddsPipe has matched across platforms."""
    match_id: int
    score: float                 # 0-100 confidence the markets are equivalent
    yes_diff: float              # absolute difference in YES price
    direction: str               # "kalshi_higher" | "polymarket_higher" | ...
    sides: List[SpreadSide]


logger = logging.getLogger(__name__)


_DEFAULT_BASE_URL = "https://oddspipe.com"


def _to_float_or_none(v: Any) -> Optional[float]:
    if v is None or v == "":
        return None
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


class OddsPipeAuthError(RuntimeError):
    """Raised when ``ODDSPIPE_API_KEY`` is missing."""


class OddsPipeDataSource(DataSource):
    name: str = "oddspipe"
    # Class default kept for tests that don't go through config; runtime
    # callers should pass ``poll_seconds`` (or stream_prices' ``poll_interval``)
    # so the operator override in ``config.ODDSPIPE_POLL_SECONDS`` actually
    # takes effect.
    refresh_interval: int = 300

    def __init__(
        self,
        api_key: Optional[str],
        *,
        base_url: str = _DEFAULT_BASE_URL,
        platforms: Iterable[str] = ("kalshi", "polymarket"),
        markets_per_platform: int = 100,
        poll_seconds: Optional[int] = None,
    ) -> None:
        self.api_key = api_key
        self.base_url = base_url.rstrip("/")
        self.platforms = tuple(platforms)
        self.markets_per_platform = int(markets_per_platform)
        if poll_seconds is not None:
            self.refresh_interval = int(poll_seconds)
        self.client = httpx.AsyncClient(
            base_url=self.base_url,
            timeout=30.0,
            headers={"X-API-Key": api_key} if api_key else {},
        )
        # Filled during fetch(). Lets fetch_spreads() resolve OddsPipe
        # internal market ids back to (platform, external_id) -> Market.id.
        self._internal_id_to_platform_pair: Dict[int, Tuple[str, str]] = {}

    def _require_key(self) -> None:
        if not self.api_key:
            raise OddsPipeAuthError(
                "ODDSPIPE_API_KEY missing. Set in secrets.local.yaml or sops."
            )

    async def fetch(self) -> List[dict]:
        """One page of markets per platform, merged.

        Skips per-platform errors so one platform 5xx doesn't kill the
        whole cycle. Returns the raw item dicts; ``normalize`` flattens
        for the runner. Side-effect: rebuilds the
        ``internal_id -> (platform, external_id)`` map used by
        :meth:`fetch_spreads`.
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

        # Rebuild the OddsPipe internal-id mapping from the fresh fetch.
        # Spreads use the top-level `id` (per /v1/markets/{id} verification)
        # — NOT the nested `source.id`, which is a different row.
        new_map: Dict[int, Tuple[str, str]] = {}
        for it in items:
            src = it.get("source") or {}
            ext_id = src.get("platform_market_id")
            platform = src.get("platform")
            internal = it.get("id")  # top-level oddspipe market id
            if internal is None or ext_id is None or platform is None:
                continue
            try:
                new_map[int(internal)] = (str(platform), str(ext_id))
            except (TypeError, ValueError):
                continue
        # Keep prior entries too — internal ids are stable, and fetch_spreads
        # may reference markets outside the top-N we just pulled.
        self._internal_id_to_platform_pair.update(new_map)
        return items

    async def _resolve_internal_id(
        self, internal_id: int
    ) -> Optional[Tuple[str, str]]:
        """Fetch /v1/markets/{id} on a cache miss to learn (platform,
        platform_market_id) for spreads referencing markets outside the
        top-N we polled this cycle."""
        cached = self._internal_id_to_platform_pair.get(internal_id)
        if cached is not None:
            return cached
        detail = await self.fetch_market_detail(internal_id)
        if detail is None:
            return None
        src = (detail.get("source") or {})
        ext_id = src.get("platform_market_id")
        platform = src.get("platform")
        if ext_id is None or platform is None:
            return None
        pair = (str(platform), str(ext_id))
        self._internal_id_to_platform_pair[internal_id] = pair
        return pair

    async def fetch_market_detail(self, internal_id: int) -> Optional[dict]:
        """GET /v1/markets/{id}. Public so callers (e.g. spread_arb signal)
        can upsert a Market row for spread sides that weren't seeded.
        """
        try:
            r = await self.client.get(f"/v1/markets/{internal_id}")
        except Exception as exc:
            logger.warning("OddsPipe /v1/markets/%s failed: %s", internal_id, exc)
            return None
        if r.status_code != 200:
            return None
        return r.json()

    async def fetch_spreads(
        self,
        *,
        min_score: float = 85.0,
        min_spread: float = 0.0,
        top_n: int = 50,
    ) -> List[SpreadMatch]:
        """Pull cross-platform matches from /v1/spreads.

        Each match has two sides (one per platform) with prices + volumes
        plus a confidence score. Use ``min_score`` to drop noisy matches
        (the API auto-matches by title similarity; <85 is mostly garbage).

        Sides whose internal id can't be resolved to a platform external_id
        get ``external_id=None`` — callers should filter those out before
        emitting a Prediction. To populate the map, call ``fetch()`` first
        (the runner does this every cycle).
        """
        self._require_key()
        try:
            r = await self.client.get(
                "/v1/spreads",
                params={
                    "min_score": str(min_score),
                    "min_spread": str(min_spread),
                    "top_n": str(top_n),
                    "limit": str(top_n),
                },
            )
        except Exception as exc:
            logger.warning("OddsPipe /v1/spreads failed: %s", exc)
            return []
        if r.status_code != 200:
            logger.warning(
                "OddsPipe /v1/spreads HTTP %s: %s", r.status_code, r.text[:200]
            )
            return []
        body = r.json()
        out: List[SpreadMatch] = []
        for item in (body.get("items") or []):
            try:
                match_id = int(item.get("match_id"))
                score = float(item.get("score") or 0.0)
            except (TypeError, ValueError):
                continue
            sides: List[SpreadSide] = []
            for platform in self.platforms:
                side_obj = item.get(platform) or {}
                if not isinstance(side_obj, dict):
                    continue
                internal = side_obj.get("market_id")
                yes = _to_float_or_none(side_obj.get("yes_price"))
                no = _to_float_or_none(side_obj.get("no_price"))
                vol = _to_float_or_none(side_obj.get("volume_usd"))
                if internal is None or yes is None:
                    continue
                try:
                    internal_int = int(internal)
                except (TypeError, ValueError):
                    continue
                pair = await self._resolve_internal_id(internal_int)
                external_id = pair[1] if pair else None
                sides.append(SpreadSide(
                    platform=platform,
                    internal_id=internal_int,
                    external_id=external_id,
                    yes_price=yes,
                    no_price=no if no is not None else (1.0 - yes),
                    volume_usd=vol if vol is not None else 0.0,
                    title=str(side_obj.get("title") or ""),
                ))
            if len(sides) < 2:
                continue
            spread_obj = item.get("spread") or {}
            yes_diff = _to_float_or_none(spread_obj.get("yes_diff")) or 0.0
            direction = str(spread_obj.get("direction") or "")
            out.append(SpreadMatch(
                match_id=match_id,
                score=score,
                yes_diff=yes_diff,
                direction=direction,
                sides=sides,
            ))
        return out

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
            description = it.get("description")
            if isinstance(description, str):
                description = description.strip() or None
            else:
                description = None
            rows.append({
                "external_id": ext_id,
                "platform": platform,
                "title": it.get("title") or ext_id,
                "taxonomy_l1": (it.get("category") or "general").lower() if it.get("category") else "general",
                "market_type": "binary",
                "status": status,
                "resolution_date": None,  # not exposed by /v1/markets
                "description": description,
            })
        return pd.DataFrame(rows)

    def validate(self, df: pd.DataFrame) -> bool:
        required = {"external_id", "platform", "title"}
        return required.issubset(df.columns) and not df.empty

    @staticmethod
    def _emit_tick(
        item: dict, *, cycle_time: Optional[pd.Timestamp] = None
    ) -> Optional[dict]:
        """Build one MarketPrice row from a /v1/markets item.

        ``cycle_time`` is the timestamp shared across the whole poll
        cycle. Passing it makes ticks within one cycle deterministic
        and lets us avoid the case where two adjacent ``pd.Timestamp.now()``
        calls on Windows return the same microsecond and collide on
        ``MarketPrice``'s composite PK across overlapping flushes.
        Falls back to ``pd.Timestamp.now()`` when the caller doesn't
        pass one (used by tests).
        """
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
            "time": cycle_time if cycle_time is not None else pd.Timestamp.now("UTC"),
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
            cycle_time = pd.Timestamp.now("UTC")
            for item in raw:
                tick = self._emit_tick(item, cycle_time=cycle_time)
                if tick is not None:
                    yield tick
            await asyncio.sleep(period)
