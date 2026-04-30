"""Stream + poll runner.

Two responsibilities:

1. `StreamProcessor` consumes a price WebSocket, batches ticks, writes to a
   raw JSONL lake AND `market_prices`. The previous implementation wrote
   `external_id` (a string) into `MarketPrice.market_id` (a UUID FK). Postgres
   rejects that; SQLite was permissive. This file resolves
   `(platform, external_id) -> Market.id` once and caches it in-memory.
2. `SourceHealthWriter` records every poll cycle into `source_health` and
   trips an emergency flag after consecutive failures (REVIEW-DECISIONS:
   `SOURCE_FAILURE_WARNING` and `SOURCE_FAILURE_CRITICAL`).
"""
from __future__ import annotations

import asyncio
import json
import logging
import os
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, Iterable, Optional, Tuple
from uuid import UUID

from sqlalchemy import select

from sigil.config import config
from sigil.db import AsyncSessionLocal, get_session, init_db
from sigil.ingestion.kalshi import KalshiDataSource
from sigil.ingestion.polymarket import PolymarketDataSource
from sigil.models import Market, MarketPrice, SourceHealth

logger = logging.getLogger(__name__)

BATCH_INTERVAL = 1.0
RAW_DATA_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "data", "raw"
)


def _next_check_time(source_name: str) -> datetime:
    """Monotonically increasing per-source timestamp.

    `source_health.PK = (check_time, source_name)` — back-to-back failure writes
    on a fast machine can collide on the same microsecond. We bump by 1us when
    that happens.
    """
    from datetime import timedelta
    now = datetime.now(timezone.utc)
    last = _LAST_RECORD_TIME.get(source_name)
    if last is not None and now <= last:
        now = last + timedelta(microseconds=1)
    _LAST_RECORD_TIME[source_name] = now
    return now


# --- emergency flags ----------------------------------------------------- #

@dataclass
class _SourceState:
    consecutive_failures: int = 0
    emergency: bool = False


_SOURCE_STATE: Dict[str, _SourceState] = {}
_LAST_RECORD_TIME: Dict[str, datetime] = {}


def is_source_emergency(source_name: str) -> bool:
    return _SOURCE_STATE.get(source_name, _SourceState()).emergency


def reset_source_state(source_name: Optional[str] = None) -> None:
    if source_name is None:
        _SOURCE_STATE.clear()
        _LAST_RECORD_TIME.clear()
    else:
        _SOURCE_STATE.pop(source_name, None)
        _LAST_RECORD_TIME.pop(source_name, None)


# --- market id cache ----------------------------------------------------- #

class MarketIdResolver:
    """In-memory cache `(platform, external_id) -> markets.id (UUID)`.

    On miss, we hit the DB once. We never cache misses — a freshly-ingested
    market can show up between subscribe and first tick.
    """

    def __init__(self) -> None:
        self._cache: Dict[Tuple[str, str], UUID] = {}

    def cache_size(self) -> int:
        return len(self._cache)

    def prime(self, items: Iterable[Tuple[str, str, UUID]]) -> None:
        for platform, external_id, market_id in items:
            self._cache[(platform, external_id)] = market_id

    async def resolve(self, session, platform: str, external_id: str) -> Optional[UUID]:
        key = (platform, external_id)
        if key in self._cache:
            return self._cache[key]
        stmt = select(Market.id).where(
            Market.platform == platform, Market.external_id == external_id
        )
        result = await session.execute(stmt)
        market_id = result.scalar_one_or_none()
        if market_id is not None:
            self._cache[key] = market_id
        return market_id


# --- source-health writer ------------------------------------------------ #

class SourceHealthWriter:
    def __init__(
        self,
        warning_threshold: int = config.SOURCE_FAILURE_WARNING,
        critical_threshold: int = config.SOURCE_FAILURE_CRITICAL,
    ) -> None:
        self.warning = warning_threshold
        self.critical = critical_threshold

    async def record(
        self,
        source_name: str,
        *,
        success: bool,
        latency_ms: Optional[int] = None,
        error_message: Optional[str] = None,
        records_fetched: Optional[int] = None,
        session=None,
    ) -> _SourceState:
        state = _SOURCE_STATE.setdefault(source_name, _SourceState())
        if success:
            state.consecutive_failures = 0
            state.emergency = False
            status = "ok"
        else:
            state.consecutive_failures += 1
            status = "error"
            if state.consecutive_failures >= self.critical:
                state.emergency = True
                logger.error(
                    "source %s CRITICAL after %d consecutive failures (refusing new orders)",
                    source_name, state.consecutive_failures,
                )
            elif state.consecutive_failures >= self.warning:
                logger.warning(
                    "source %s WARNING after %d consecutive failures",
                    source_name, state.consecutive_failures,
                )

        check_time = _next_check_time(source_name)
        row = SourceHealth(
            check_time=check_time,
            source_name=source_name,
            status=status,
            latency_ms=latency_ms,
            error_message=error_message,
            records_fetched=records_fetched,
        )

        if session is not None:
            session.add(row)
        else:
            async with get_session() as s:
                s.add(row)
        return state


# --- stream processor ---------------------------------------------------- #

class StreamProcessor:
    def __init__(
        self,
        source_name: str,
        platform: str,
        cache_file: str,
        resolver: Optional[MarketIdResolver] = None,
    ) -> None:
        self.source_name = source_name
        self.platform = platform
        self.cache_file = cache_file
        self.resolver = resolver or MarketIdResolver()
        self.batch: list[dict] = []
        self.dropped_unknown_market = 0

    async def flush_batch(self) -> None:
        while True:
            await asyncio.sleep(BATCH_INTERVAL)
            await self._flush_once()

    async def _flush_once(self) -> int:
        if not self.batch:
            return 0
        current_batch = self.batch
        self.batch = []

        try:
            with open(self.cache_file, "a") as f:
                for item in current_batch:
                    item_copy = dict(item)
                    if isinstance(item_copy.get("time"), datetime):
                        item_copy["time"] = item_copy["time"].isoformat()
                    f.write(json.dumps(item_copy, default=str) + "\n")
        except Exception:
            logger.exception("failed writing JSONL lake for %s", self.source_name)

        async with get_session() as session:
            inserted = 0
            for item in current_batch:
                external_id = item.get("market_id")
                if not external_id:
                    continue
                market_id = await self.resolver.resolve(session, self.platform, external_id)
                if market_id is None:
                    self.dropped_unknown_market += 1
                    continue
                time_val = item.get("time")
                if isinstance(time_val, str):
                    from dateutil.parser import parse  # local import keeps cold-start cheap
                    time_val = parse(time_val)
                if time_val is None:
                    time_val = datetime.now(timezone.utc)

                session.add(
                    MarketPrice(
                        time=time_val,
                        market_id=market_id,
                        source=item.get("source", self.source_name),
                        bid=item.get("bid"),
                        ask=item.get("ask"),
                        last_price=item.get("last_price"),
                        volume_24h=item.get("volume_24h"),
                        open_interest=item.get("open_interest"),
                    )
                )
                inserted += 1
        logger.info(
            "[%s] flushed %d ticks (dropped_unknown=%d, cache_size=%d)",
            self.source_name, inserted, self.dropped_unknown_market, self.resolver.cache_size(),
        )
        return inserted

    async def consume_stream(self, source: Any, market_ids: list[str]) -> None:
        logger.info("[%s] streaming %d markets", self.source_name, len(market_ids))
        try:
            async for tick in source.stream_prices(market_ids):
                self.batch.append(tick)
        except Exception:
            logger.exception("[%s] stream error", self.source_name)


# --- bootstrap orchestration --------------------------------------------- #

async def _seed_kalshi(kalshi_source: KalshiDataSource, resolver: MarketIdResolver) -> list[str]:
    kalshi_ids: list[str] = []
    try:
        kal_raw = await kalshi_source.fetch()
        kal_df = kalshi_source.normalize(kal_raw)
        top_10 = kal_df.head(10).to_dict("records")
    except Exception as exc:
        logger.warning("Kalshi fetch failed (%s); using sample seed", exc)
        top_10 = [
            {"external_id": "KAL-BTC-100K", "title": "Will Bitcoin reach $100k by EOY?", "taxonomy_l1": "crypto"},
            {"external_id": "KAL-FED-DEC", "title": "Will the Fed cut rates in December?", "taxonomy_l1": "economics"},
            {"external_id": "KAL-NFL-KC", "title": "Will the Chiefs win the Super Bowl?", "taxonomy_l1": "sports"},
        ]
    async with get_session() as session:
        for m in top_10:
            ext_id = m["external_id"]
            kalshi_ids.append(ext_id)
            existing = await session.execute(
                select(Market).where(Market.platform == "kalshi", Market.external_id == ext_id)
            )
            market = existing.scalars().first()
            if market is None:
                market = Market(
                    platform="kalshi",
                    external_id=ext_id,
                    title=m.get("title", ext_id),
                    taxonomy_l1=m.get("taxonomy_l1", "general"),
                    market_type="binary",
                    status="open",
                )
                session.add(market)
                await session.flush()
            resolver.prime([("kalshi", ext_id, market.id)])
    return kalshi_ids


async def run_ingestion() -> None:
    await init_db()
    os.makedirs(RAW_DATA_DIR, exist_ok=True)

    kalshi_source = KalshiDataSource()
    poly_source = PolymarketDataSource()
    health = SourceHealthWriter()
    resolver = MarketIdResolver()

    kalshi_ids = await _seed_kalshi(kalshi_source, resolver)
    await health.record("kalshi", success=True, records_fetched=len(kalshi_ids))

    kalshi_processor = StreamProcessor(
        "Kalshi", "kalshi", os.path.join(RAW_DATA_DIR, "kalshi_ticks.jsonl"), resolver
    )
    poly_processor = StreamProcessor(
        "Polymarket", "polymarket", os.path.join(RAW_DATA_DIR, "polymarket_ticks.jsonl"), resolver
    )

    await asyncio.gather(
        kalshi_processor.consume_stream(kalshi_source, kalshi_ids),
        poly_processor.consume_stream(poly_source, []),
        kalshi_processor.flush_batch(),
        poly_processor.flush_batch(),
    )


if __name__ == "__main__":
    try:
        asyncio.run(run_ingestion())
    except KeyboardInterrupt:
        logger.info("ingestion stopped")
