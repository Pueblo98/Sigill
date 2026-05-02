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
from typing import Any, Dict, Iterable, List, Optional, Tuple
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from sigil.config import config
from sigil.db import AsyncSessionLocal, get_session, init_db
from sigil.decision.loop import run_decision_loop
from sigil.ingestion.kalshi import KalshiDataSource
from sigil.ingestion.oddspipe import OddsPipeDataSource
from sigil.ingestion.orderbook_archive import OrderbookArchive
from sigil.ingestion.polymarket import PolymarketDataSource
from sigil.models import Market, MarketOrderbook, MarketPrice, SourceHealth
from sigil.signals.elo_sports import generate_elo_predictions
from sigil.signals.spread_arb import generate_spread_predictions

logger = logging.getLogger(__name__)

BATCH_INTERVAL = 1.0
# Repo root is 4 dirnames up from src/sigil/ingestion/runner.py:
# runner.py -> ingestion -> sigil -> src -> repo_root
RAW_DATA_DIR = os.path.join(
    os.path.dirname(
        os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
    ),
    "data",
    "raw",
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
        archive: Optional[OrderbookArchive] = None,
    ) -> None:
        self.source_name = source_name
        self.platform = platform
        self.cache_file = cache_file
        self.resolver = resolver or MarketIdResolver()
        self.archive = archive
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

        if self.archive is not None:
            try:
                self.archive.write_batch(self.platform, current_batch)
            except Exception:
                logger.exception(
                    "failed writing orderbook archive for %s", self.source_name
                )

        # Dedup per (market_id, source) within the batch — Polymarket
        # emits multiple price_changes in a single WS message and we can
        # write multiple ticks at the same microsecond, which collides
        # with MarketPrice's (time, market_id, source) composite PK.
        # The full high-frequency record still lives in the JSONL lake
        # and the orderbook archive; MarketPrice keeps the last per
        # (market_id, source) per batch.
        latest_per_key: Dict[Tuple[str, str], dict] = {}
        for item in current_batch:
            ext = item.get("market_id")
            if not ext:
                continue
            key = (ext, item.get("source", self.source_name))
            latest_per_key[key] = item

        async with get_session() as session:
            inserted = 0
            for item in latest_per_key.values():
                external_id = item.get("market_id")
                # Per-tick platform — OddsPipe is a single source covering
                # both kalshi and polymarket, so tick.platform may differ
                # from self.platform. Falls back to self.platform when the
                # tick doesn't carry one (legacy WS adapters).
                tick_platform = item.get("platform") or self.platform
                market_id = await self.resolver.resolve(session, tick_platform, external_id)
                if market_id is None:
                    self.dropped_unknown_market += 1
                    continue
                time_val = item.get("time")
                if isinstance(time_val, str):
                    from dateutil.parser import parse  # local import keeps cold-start cheap
                    time_val = parse(time_val)
                if time_val is None:
                    time_val = datetime.now(timezone.utc)

                source_name = item.get("source", self.source_name)
                # Per-row SAVEPOINT so a cross-batch collision on the
                # (time, market_id, source) composite PK doesn't poison
                # the whole flush. In-batch dedup already handles the
                # within-batch case; cross-batch dupes are rarer (Windows
                # clock collision on a 1-second OddsPipe poll boundary)
                # and benign — drop and keep going. Works on both
                # Postgres and SQLite.
                try:
                    async with session.begin_nested():
                        session.add(
                            MarketPrice(
                                time=time_val,
                                market_id=market_id,
                                source=source_name,
                                bid=item.get("bid"),
                                ask=item.get("ask"),
                                last_price=item.get("last_price"),
                                volume_24h=item.get("volume_24h"),
                                open_interest=item.get("open_interest"),
                            )
                        )
                except IntegrityError:
                    # Already inserted by a previous flush; fine, skip.
                    continue
                inserted += 1
                # Persist the latest ladder snapshot when the upstream
                # adapter provides one. OddsPipe ticks set bids/asks=[]
                # so this is a no-op for REST-polled rows; only direct
                # exchange WS feeds (Kalshi / Polymarket) populate this.
                bids = item.get("bids") or []
                asks = item.get("asks") or []
                if bids or asks:
                    await self._upsert_orderbook_snapshot(
                        session,
                        market_id=market_id,
                        source=source_name,
                        bids=bids,
                        asks=asks,
                        updated_at=time_val,
                    )
        logger.info(
            "[%s] flushed %d ticks (dropped_unknown=%d, cache_size=%d)",
            self.source_name, inserted, self.dropped_unknown_market, self.resolver.cache_size(),
        )
        return inserted

    @staticmethod
    def _normalize_ladder(rungs: list, max_levels: int = 25) -> list:
        """Reduce ladder entries to a clean list of ``[price, size]`` pairs.

        Polymarket emits ``[{"price": "0.43", "size": "120"}, ...]``;
        Kalshi emits ``[[42, 1500], [41, 800], ...]`` (price in cents).
        Both shapes are normalised to ``[[float_price_in_dollars,
        float_size], ...]`` and capped at ``max_levels`` so a 1000-deep
        book doesn't bloat one row.
        """
        out: list[list[float]] = []
        for entry in rungs[:max_levels]:
            try:
                if isinstance(entry, dict):
                    p = float(entry.get("price"))
                    s = float(entry.get("size", 0) or 0)
                elif isinstance(entry, (list, tuple)) and len(entry) >= 2:
                    p_raw, s_raw = entry[0], entry[1]
                    p = float(p_raw)
                    s = float(s_raw or 0)
                    # Kalshi-style integer cents heuristic: prices > 1 are
                    # almost certainly cents.
                    if p > 1.0:
                        p = p / 100.0
                else:
                    continue
            except (TypeError, ValueError):
                continue
            out.append([p, s])
        return out

    async def _upsert_orderbook_snapshot(
        self,
        session: Any,
        *,
        market_id: UUID,
        source: str,
        bids: list,
        asks: list,
        updated_at: datetime,
    ) -> None:
        """Upsert the latest top-N ladder for this (market, source).

        Falls back to a SELECT-then-update so we don't depend on the
        Postgres-specific ON CONFLICT helper just for one table.
        """
        bids_norm = self._normalize_ladder(bids)
        asks_norm = self._normalize_ladder(asks)
        existing = (await session.execute(
            select(MarketOrderbook).where(
                MarketOrderbook.market_id == market_id,
                MarketOrderbook.source == source,
            )
        )).scalar_one_or_none()
        if existing is None:
            session.add(MarketOrderbook(
                market_id=market_id,
                source=source,
                bids_json=bids_norm,
                asks_json=asks_norm,
                updated_at=updated_at,
            ))
        else:
            existing.bids_json = bids_norm
            existing.asks_json = asks_norm
            existing.updated_at = updated_at

    async def consume_stream(self, source: Any, market_ids: list[str]) -> None:
        # Some sources (OddsPipe) ignore market_ids and discover their own
        # set per cycle; the count is informational only.
        if market_ids:
            logger.info("[%s] streaming %d markets", self.source_name, len(market_ids))
        else:
            logger.info("[%s] streaming (source-driven discovery)", self.source_name)
        try:
            async for tick in source.stream_prices(market_ids):
                self.batch.append(tick)
        except Exception:
            logger.exception("[%s] stream error", self.source_name)


# --- bootstrap orchestration --------------------------------------------- #

async def _upsert_markets(
    rows: Iterable[dict],
    platform: str,
    resolver: MarketIdResolver,
) -> list[str]:
    """Insert missing Markets, opportunistically fill description/archived
    on existing rows, and prime the id resolver. Returns external_ids in
    input order.

    Existing markets get their description filled when it's currently NULL
    and the adapter has provided one (Polymarket gamma supplies it; Kalshi
    can't until auth lands). The archived flag is mirrored from the source
    on every cycle so Polymarket flips on /off automatically.
    """
    out: list[str] = []
    async with get_session() as session:
        for m in rows:
            ext_id = m.get("external_id")
            if not ext_id:
                continue
            out.append(ext_id)
            existing = await session.execute(
                select(Market).where(
                    Market.platform == platform, Market.external_id == ext_id
                )
            )
            market = existing.scalars().first()
            description = m.get("description")
            archived = m.get("archived")
            if market is None:
                market = Market(
                    platform=platform,
                    external_id=ext_id,
                    title=m.get("title", ext_id),
                    taxonomy_l1=m.get("taxonomy_l1", "general"),
                    market_type="binary",
                    status="open",
                    description=description,
                    archived=bool(archived) if archived is not None else False,
                )
                session.add(market)
                await session.flush()
            else:
                # Backfill description on existing markets when adapter has
                # one and we don't yet — keeps the column populated as
                # adapters mature without stomping operator-edited text.
                if description and not market.description:
                    market.description = description
                # Mirror archived flag every cycle (source of truth).
                if archived is not None:
                    market.archived = bool(archived)
                # Promote a real category over the 'general' default when
                # the adapter provides one.
                tax = m.get("taxonomy_l1")
                if tax and tax != "general" and (market.taxonomy_l1 or "general") == "general":
                    market.taxonomy_l1 = tax
            resolver.prime([(platform, ext_id, market.id)])
    return out


async def _seed_kalshi(
    kalshi_source: KalshiDataSource, resolver: MarketIdResolver, *, top_n: int = 25
) -> list[str]:
    """Fetch the first page of Kalshi markets and upsert them.

    Without auth (config.KALSHI_KEY_ID unset), fetch() logs and returns []
    — we fall back to a tiny hand-curated set so the pipeline still
    boots end-to-end.
    """
    try:
        raw = await kalshi_source.fetch(limit=top_n)
        df = kalshi_source.normalize(raw)
        rows = df.head(top_n).to_dict("records")
    except Exception as exc:
        logger.warning("Kalshi fetch failed (%s); using sample seed", exc)
        rows = []
    if not rows:
        rows = [
            {"external_id": "KXFEDDEC-DEC25-CUT",
             "title": "Will the Fed cut rates in December?",
             "taxonomy_l1": "economics"},
        ]
    return await _upsert_markets(rows, "kalshi", resolver)


async def _seed_polymarket(
    poly_source: PolymarketDataSource, resolver: MarketIdResolver, *, top_n: int = 25
) -> list[str]:
    """Fetch top-volume Polymarket markets, upsert, and return YES-side
    token ids ready to pass into ``stream_prices`` (the WS subscribes
    on token ids, not condition_ids)."""
    try:
        raw = await poly_source.fetch(limit=top_n)
        df = poly_source.normalize(raw)
        rows = df.head(top_n).to_dict("records")
    except Exception as exc:
        logger.warning("Polymarket fetch failed (%s)", exc)
        return []
    await _upsert_markets(rows, "polymarket", resolver)
    return poly_source.yes_token_ids


async def _run_elo_sports_loop() -> None:
    """Periodic Elo signal generator. Runs against open Kalshi NBA
    markets seeded by the OddsPipe stream. Standalone — doesn't depend
    on the OddsPipe data source instance.
    """
    await asyncio.sleep(20)
    interval = max(60, int(config.ELO_SPORTS_INTERVAL_SECONDS))
    while True:
        try:
            async with AsyncSessionLocal() as session:
                n = await generate_elo_predictions(
                    session,
                    min_edge=config.ELO_SPORTS_MIN_EDGE,
                    confidence=config.ELO_SPORTS_CONFIDENCE,
                    dedup_window_seconds=interval,
                )
            if n > 0:
                logger.info("elo_sports: wrote %d Prediction(s)", n)
        except Exception:
            logger.exception("elo_sports loop iteration failed")
        await asyncio.sleep(interval)


async def _run_spread_arb_loop(odds_source: OddsPipeDataSource) -> None:
    """Periodically poll /v1/spreads and emit Predictions.

    Runs forever; cancellation propagates from ``run_ingestion``'s
    asyncio.gather. Sleeps a few seconds before the first run so the
    OddsPipe internal-id map (built by the OddsPipe stream's first
    fetch) is populated.
    """
    await asyncio.sleep(5)
    interval = max(60, int(config.SPREAD_ARB_INTERVAL_SECONDS))
    while True:
        try:
            async with AsyncSessionLocal() as session:
                n = await generate_spread_predictions(
                    session,
                    odds_source,
                    min_score=config.SPREAD_ARB_MIN_SCORE,
                    min_edge=config.SPREAD_ARB_MIN_EDGE,
                    max_yes_diff=config.SPREAD_ARB_MAX_YES_DIFF,
                    dedup_window_seconds=interval,
                    max_matches=config.SPREAD_ARB_MAX_MATCHES,
                )
            if n > 0:
                logger.info("spread_arb: wrote %d Prediction(s)", n)
        except Exception:
            logger.exception("spread_arb loop iteration failed")
        await asyncio.sleep(interval)


async def _seed_oddspipe(
    odds_source: OddsPipeDataSource, resolver: MarketIdResolver
) -> int:
    """Fetch one page from each platform via OddsPipe, upsert markets per
    platform, prime the resolver. Returns the total count seeded.
    """
    try:
        raw = await odds_source.fetch()
        df = odds_source.normalize(raw)
    except Exception as exc:
        logger.warning("OddsPipe fetch failed (%s)", exc)
        return 0
    if df.empty:
        return 0
    n = 0
    for platform in df["platform"].unique().tolist():
        platform_rows = df[df["platform"] == platform].to_dict("records")
        seeded = await _upsert_markets(platform_rows, platform, resolver)
        n += len(seeded)
    return n


async def run_ingestion() -> None:
    await init_db()
    os.makedirs(RAW_DATA_DIR, exist_ok=True)

    health = SourceHealthWriter()
    resolver = MarketIdResolver()

    archive: Optional[OrderbookArchive] = None
    if config.ORDERBOOK_ARCHIVE_ENABLED:
        os.makedirs(config.ORDERBOOK_ARCHIVE_DIR, exist_ok=True)
        archive = OrderbookArchive(
            root_dir=config.ORDERBOOK_ARCHIVE_DIR,
            max_open_handles=config.ORDERBOOK_ARCHIVE_MAX_OPEN_HANDLES,
        )
        logger.info(
            "orderbook archive enabled: dir=%s max_open=%d",
            config.ORDERBOOK_ARCHIVE_DIR,
            config.ORDERBOOK_ARCHIVE_MAX_OPEN_HANDLES,
        )

    coros: list = []

    # ---- OddsPipe (default path) ---------------------------------------- #
    odds_source: Optional[OddsPipeDataSource] = None
    if config.ODDSPIPE_API_KEY:
        odds_source = OddsPipeDataSource(
            api_key=config.ODDSPIPE_API_KEY,
            base_url=config.ODDSPIPE_BASE_URL,
            markets_per_platform=config.ODDSPIPE_MARKETS_PER_PLATFORM,
            poll_seconds=config.ODDSPIPE_POLL_SECONDS,
        )
        odds_seeded = await _seed_oddspipe(odds_source, resolver)
        await health.record(
            "oddspipe", success=True, records_fetched=odds_seeded
        )
        logger.info("OddsPipe key configured — seeded %d markets", odds_seeded)
        odds_processor = StreamProcessor(
            "OddsPipe", "kalshi",  # platform fallback; ticks carry their own platform
            os.path.join(RAW_DATA_DIR, "oddspipe_ticks.jsonl"),
            resolver, archive=archive,
        )
        coros.append(odds_processor.consume_stream(odds_source, []))
        coros.append(odds_processor.flush_batch())

        # Spread-arb signal generator runs alongside as its own coroutine.
        # Reuses the same OddsPipeDataSource (and its internal-id map).
        if config.SPREAD_ARB_INTERVAL_SECONDS > 0:
            coros.append(_run_spread_arb_loop(odds_source))
            logger.info(
                "spread_arb signal enabled (interval=%ds, min_score=%.1f, min_edge=%.2f)",
                config.SPREAD_ARB_INTERVAL_SECONDS,
                config.SPREAD_ARB_MIN_SCORE,
                config.SPREAD_ARB_MIN_EDGE,
            )

    # ---- Elo sports signal (independent of OddsPipe) ------------------ #
    if config.ELO_SPORTS_INTERVAL_SECONDS > 0:
        coros.append(_run_elo_sports_loop())
        logger.info(
            "elo_sports signal enabled (interval=%ds, min_edge=%.2f)",
            config.ELO_SPORTS_INTERVAL_SECONDS, config.ELO_SPORTS_MIN_EDGE,
        )

    # ---- Decision-engine loop ------------------------------------------ #
    # Independent of OddsPipe — runs whenever any signal is producing
    # Predictions (spread_arb, elo_sports, or future models).
    if config.DECISION_LOOP_INTERVAL_SECONDS > 0:
        coros.append(run_decision_loop(AsyncSessionLocal))
        logger.info(
            "decision_loop scheduled (interval=%ds, mode=%s)",
            config.DECISION_LOOP_INTERVAL_SECONDS, config.DEFAULT_MODE,
        )
    else:
        logger.warning(
            "ODDSPIPE_API_KEY not set — no markets will flow. "
            "Drop the key in secrets.local.yaml or enable DIRECT_EXCHANGE_WS_ENABLED."
        )

    # ---- Direct Kalshi/Polymarket WS (opt-in) --------------------------- #
    if config.DIRECT_EXCHANGE_WS_ENABLED:
        kalshi_source = KalshiDataSource()
        poly_source = PolymarketDataSource()
        kalshi_ids = await _seed_kalshi(kalshi_source, resolver)
        await health.record("kalshi", success=True, records_fetched=len(kalshi_ids))
        poly_token_ids = await _seed_polymarket(poly_source, resolver)
        await health.record(
            "polymarket", success=True, records_fetched=len(poly_token_ids)
        )
        kalshi_processor = StreamProcessor(
            "Kalshi", "kalshi", os.path.join(RAW_DATA_DIR, "kalshi_ticks.jsonl"),
            resolver, archive=archive,
        )
        poly_processor = StreamProcessor(
            "Polymarket", "polymarket",
            os.path.join(RAW_DATA_DIR, "polymarket_ticks.jsonl"),
            resolver, archive=archive,
        )
        coros.extend([
            kalshi_processor.consume_stream(kalshi_source, kalshi_ids),
            poly_processor.consume_stream(poly_source, poly_token_ids),
            kalshi_processor.flush_batch(),
            poly_processor.flush_batch(),
        ])
        logger.info(
            "Direct exchange WS enabled — Kalshi (%d markets) + Polymarket (%d tokens)",
            len(kalshi_ids), len(poly_token_ids),
        )

    if not coros:
        logger.warning(
            "run_ingestion has no sources configured; exiting. "
            "Set ODDSPIPE_API_KEY or DIRECT_EXCHANGE_WS_ENABLED."
        )
        if archive is not None:
            archive.close()
        return

    try:
        await asyncio.gather(*coros)
    finally:
        if archive is not None:
            archive.close()


if __name__ == "__main__":
    try:
        asyncio.run(run_ingestion())
    except KeyboardInterrupt:
        logger.info("ingestion stopped")
