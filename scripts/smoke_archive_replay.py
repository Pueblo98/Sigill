"""Smoke test for the orderbook-archive replay reader (TODO-9).

Writes a few ticks via ``OrderbookArchive``, reads them back via
``iter_archive_ticks + load_market_id_map``, then runs them through a
minimal ``Backtester`` to confirm the round-trip plays through the
engine cleanly. Exits non-zero on first mismatch.

Usage:

    .venv/Scripts/python.exe scripts/smoke_archive_replay.py
"""
from __future__ import annotations

import asyncio
import os
import shutil
import sys
import tempfile
from datetime import date, datetime, timedelta, timezone
from uuid import uuid4

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = os.path.join(ROOT, "src")
if SRC not in sys.path:
    sys.path.insert(0, SRC)

import sigil.db as sigil_db
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from sigil.backtesting.engine import (
    BacktestConfig,
    Backtester,
    PriceTick,
    Signal,
)
from sigil.backtesting.replay import iter_archive_ticks, load_market_id_map
from sigil.db import Base
import sigil.models  # noqa: F401  (registers tables on Base.metadata)
from sigil.ingestion.orderbook_archive import OrderbookArchive
from sigil.models import Market


def _ok(label: str) -> None:
    print(f"[ OK ] {label}")


def _fail(label: str, detail: str = "") -> None:
    print(f"[FAIL] {label}: {detail}")
    sys.exit(1)


class _BuyOnceStrategy:
    def __init__(self, market_id, limit_price=0.40):
        self.market_id = market_id
        self.limit_price = limit_price
        self._fired = False

    def generate_signals(self, event, portfolio_state):
        if self._fired or not isinstance(event, PriceTick):
            return []
        self._fired = True
        return [Signal(
            market_id=self.market_id, side="buy", outcome="yes",
            quantity=10, order_type="limit", limit_price=self.limit_price,
        )]


async def main() -> None:
    tmp = tempfile.mkdtemp(prefix="sigil_replay_smoke_")
    db_url = f"sqlite+aiosqlite:///{tmp}/smoke.db"
    archive_dir = os.path.join(tmp, "archive")
    print(f"--- archive replay smoke (tmp={tmp}) ---")

    engine = create_async_engine(db_url, echo=False, future=True)
    factory = async_sessionmaker(bind=engine, expire_on_commit=False)
    sigil_db.engine = engine
    sigil_db.AsyncSessionLocal = factory
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    market = Market(
        id=uuid4(),
        platform="kalshi",
        external_id="MKT-A",
        title="Replay smoke",
        taxonomy_l1="general",
        market_type="binary",
        status="open",
    )
    async with factory() as session:
        session.add(market)
        await session.commit()
    _ok("seeded 1 market in scratch DB")

    archive = OrderbookArchive(archive_dir, max_open_handles=4)
    base = datetime(2026, 5, 1, 12, 0, 0, tzinfo=timezone.utc)
    prices = [0.45, 0.42, 0.44, 0.46, 0.48]
    archive.write_batch("kalshi", [
        {"market_id": "MKT-A", "platform": "kalshi",
         "time": base + timedelta(minutes=i),
         "bid": p - 0.01, "ask": p + 0.01, "last_price": p,
         "volume_24h": 1000.0 + i,
         "bids": [[int((p - 0.01) * 100), 100]],
         "asks": [[int((p + 0.01) * 100), 100]],
         "source": "exchange_ws"}
        for i, p in enumerate(prices)
    ])
    archive.close()
    _ok(f"wrote {len(prices)} ticks via OrderbookArchive")

    async with factory() as session:
        market_id_map = await load_market_id_map(session, platform="kalshi")
    if (("kalshi", "MKT-A")) not in market_id_map:
        _fail("load_market_id_map", "MKT-A not resolved")
    _ok(f"load_market_id_map returned {len(market_id_map)} entry/entries")

    ticks = list(iter_archive_ticks(
        archive_dir,
        market_id_map=market_id_map,
        start_date=date(2026, 5, 1),
        end_date=date(2026, 5, 1),
    ))
    if len(ticks) != len(prices):
        _fail("tick count round-trip", f"expected {len(prices)}, got {len(ticks)}")
    if [t.trade_price for t in ticks] != prices:
        _fail("trade_price ordering", str([t.trade_price for t in ticks]))
    if not all(t.market_id == market.id for t in ticks):
        _fail("market_id resolution", "some ticks point at the wrong UUID")
    _ok("iter_archive_ticks yielded all ticks chronologically with resolved UUIDs")

    cfg = BacktestConfig(
        start_date=ticks[0].timestamp,
        end_date=ticks[-1].timestamp,
        initial_capital=5000.0,
    )
    result = Backtester(_BuyOnceStrategy(market.id), ticks, cfg).run()
    if len(result.equity_curve) != len(ticks):
        _fail("equity curve length", f"expected {len(ticks)}, got {len(result.equity_curve)}")
    _ok(
        f"Backtester(... data_iter=ticks).run() processed {len(result.equity_curve)} events; "
        f"trades={len(result.trades)} final_equity={result.final_equity:.2f}"
    )

    await engine.dispose()
    shutil.rmtree(tmp, ignore_errors=True)
    print("\n[ OK ] all archive replay smoke assertions passed")


if __name__ == "__main__":
    asyncio.run(main())
