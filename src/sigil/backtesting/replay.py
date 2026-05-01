"""Replay reader for the per-market per-day Kalshi orderbook archive.

Reads JSONL files written by ``sigil.ingestion.orderbook_archive`` and
yields :class:`PriceTick` instances ready to feed into ``Backtester(
data_iter=...)``. Pure I/O — the caller resolves
``(platform, external_id) -> Market.id (UUID)`` once via
:func:`load_market_id_map` and passes the mapping in. Markets without a
mapping are skipped (logged once each).

The companion writer is ``sigil.ingestion.orderbook_archive``; the
JSONL format is the contract between them.
"""
from __future__ import annotations

import json
import logging
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Dict, Iterable, Iterator, Optional, Tuple
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from sigil.backtesting.engine import PriceTick
from sigil.models import Market

logger = logging.getLogger(__name__)


def _daterange(start: date, end: date) -> Iterator[date]:
    if end < start:
        return
    cur = start
    while cur <= end:
        yield cur
        cur += timedelta(days=1)


def _coerce_time(raw: object) -> Optional[datetime]:
    if isinstance(raw, str):
        try:
            from dateutil.parser import parse  # local import: cold-start cheap

            dt = parse(raw)
            return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)
        except Exception:
            return None
    return None


def _record_to_pricetick(rec: dict, market_id: UUID) -> Optional[PriceTick]:
    ts = _coerce_time(rec.get("time"))
    if ts is None:
        return None
    return PriceTick(
        timestamp=ts,
        market_id=market_id,
        bid=rec.get("bid"),
        ask=rec.get("ask"),
        trade_price=rec.get("last_price"),
        volume_24h=rec.get("volume_24h"),
    )


def iter_archive_ticks(
    archive_dir: str | Path,
    *,
    market_id_map: Dict[Tuple[str, str], UUID],
    start_date: date,
    end_date: date,
    platform: str = "kalshi",
    external_ids: Optional[Iterable[str]] = None,
) -> Iterator[PriceTick]:
    """Yield PriceTicks across ``[start_date, end_date]`` (inclusive, UTC).

    Reads every ``<archive_dir>/<platform>/<external_id>/<YYYY-MM-DD>.jsonl``
    in range, parses each line, and yields the result sorted by
    ``timestamp``. Multi-day, multi-market input is collected then sorted
    in-memory; for a single Kalshi market that fits comfortably (decision
    4E says backtests are batch jobs, no <5 min SLA, so latency budget is
    generous).

    Args:
        archive_dir: ``config.ORDERBOOK_ARCHIVE_DIR``.
        market_id_map: ``{(platform, external_id): Market.id}``. Build via
            :func:`load_market_id_map`. Markets not in the map are skipped
            (one warning each).
        start_date, end_date: inclusive UTC date range.
        platform: subdirectory under ``archive_dir`` to scan; default
            ``"kalshi"``.
        external_ids: optional whitelist of external tickers; ``None``
            means every market directory found under ``platform``.
    """
    root = Path(archive_dir) / platform
    if not root.exists():
        logger.warning("orderbook archive root missing: %s", root)
        return

    if external_ids is not None:
        wanted = list(external_ids)
        market_dirs = [root / ext for ext in wanted if (root / ext).is_dir()]
    else:
        market_dirs = sorted(d for d in root.iterdir() if d.is_dir())

    ticks: list[PriceTick] = []
    missing_resolution: set[str] = set()

    for market_dir in market_dirs:
        external_id = market_dir.name
        market_id = market_id_map.get((platform, external_id))
        if market_id is None:
            if external_id not in missing_resolution:
                missing_resolution.add(external_id)
                logger.warning(
                    "archive replay: no Market.id for (%s, %s); skipping",
                    platform, external_id,
                )
            continue

        for d in _daterange(start_date, end_date):
            file_path = market_dir / f"{d.isoformat()}.jsonl"
            if not file_path.exists():
                continue
            with file_path.open("r", encoding="utf-8") as f:
                for lineno, line in enumerate(f, start=1):
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        rec = json.loads(line)
                    except json.JSONDecodeError:
                        logger.warning(
                            "archive replay: malformed JSON at %s:%d; skipping",
                            file_path, lineno,
                        )
                        continue
                    tick = _record_to_pricetick(rec, market_id)
                    if tick is None:
                        logger.warning(
                            "archive replay: tick missing time at %s:%d; skipping",
                            file_path, lineno,
                        )
                        continue
                    ticks.append(tick)

    ticks.sort(key=lambda t: t.timestamp)
    yield from ticks


async def load_market_id_map(
    session: AsyncSession,
    platform: str = "kalshi",
) -> Dict[Tuple[str, str], UUID]:
    """One-shot DB resolve of every ``Market`` for ``platform``.

    Returns ``{(platform, external_id): Market.id}``. Pass straight to
    :func:`iter_archive_ticks`.
    """
    stmt = select(Market.external_id, Market.id).where(Market.platform == platform)
    rows = (await session.execute(stmt)).all()
    return {(platform, ext): mid for ext, mid in rows}
