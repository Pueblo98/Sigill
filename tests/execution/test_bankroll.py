"""W2.2(b) — bankroll snapshot writer tests."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from uuid import uuid4

import pytest
from sqlalchemy import select

from sigil.config import config
from sigil.execution.bankroll import snapshot_bankroll
from sigil.models import BankrollSnapshot, Position


@pytest.mark.asyncio
async def test_snapshot_writes_row_with_initial_bankroll_when_no_positions(session):
    snap = await snapshot_bankroll(session, mode="paper")
    assert snap.mode == "paper"
    assert snap.equity == pytest.approx(config.BANKROLL_INITIAL)
    assert snap.realized_pnl_total == pytest.approx(0.0)
    assert snap.unrealized_pnl_total == pytest.approx(0.0)
    assert snap.settled_trades_total == 0
    assert snap.settled_trades_30d == 0


@pytest.mark.asyncio
async def test_snapshot_aggregates_realized_and_unrealized_pnl(session, sample_market):
    open_pos = Position(
        id=uuid4(),
        platform="kalshi",
        market_id=sample_market.id,
        mode="paper",
        outcome="yes",
        quantity=10,
        avg_entry_price=0.40,
        unrealized_pnl=12.0,
        realized_pnl=0.0,
        status="open",
    )
    closed_pos = Position(
        id=uuid4(),
        platform="kalshi",
        market_id=sample_market.id,
        mode="paper",
        outcome="no",
        quantity=0,
        avg_entry_price=0.55,
        unrealized_pnl=0.0,
        realized_pnl=33.5,
        status="closed",
        closed_at=datetime.now(timezone.utc),
    )
    session.add_all([open_pos, closed_pos])
    await session.commit()

    snap = await snapshot_bankroll(session, mode="paper")
    assert snap.realized_pnl_total == pytest.approx(33.5)
    assert snap.unrealized_pnl_total == pytest.approx(12.0)
    assert snap.equity == pytest.approx(config.BANKROLL_INITIAL + 33.5 + 12.0)
    assert snap.settled_trades_total == 1
    assert snap.settled_trades_30d == 1


@pytest.mark.asyncio
async def test_snapshot_settled_count_excludes_other_mode(session, sample_market):
    paper_closed = Position(
        id=uuid4(),
        platform="kalshi",
        market_id=sample_market.id,
        mode="paper",
        outcome="yes",
        quantity=0,
        avg_entry_price=0.5,
        realized_pnl=10.0,
        status="closed",
        closed_at=datetime.now(timezone.utc),
    )
    live_closed = Position(
        id=uuid4(),
        platform="kalshi",
        market_id=sample_market.id,
        mode="live",
        outcome="yes",
        quantity=0,
        avg_entry_price=0.5,
        realized_pnl=999.0,
        status="closed",
        closed_at=datetime.now(timezone.utc),
    )
    session.add_all([paper_closed, live_closed])
    await session.commit()

    snap = await snapshot_bankroll(session, mode="paper")
    assert snap.settled_trades_total == 1
    assert snap.realized_pnl_total == pytest.approx(10.0)


@pytest.mark.asyncio
async def test_snapshot_30d_window_excludes_old_settles(session, sample_market):
    long_ago = datetime.now(timezone.utc) - timedelta(days=config.DRAWDOWN_WINDOW_DAYS + 5)
    old_closed = Position(
        id=uuid4(),
        platform="kalshi",
        market_id=sample_market.id,
        mode="paper",
        outcome="yes",
        quantity=0,
        avg_entry_price=0.5,
        realized_pnl=5.0,
        status="closed",
        closed_at=long_ago,
    )
    recent_closed = Position(
        id=uuid4(),
        platform="kalshi",
        market_id=sample_market.id,
        mode="paper",
        outcome="no",
        quantity=0,
        avg_entry_price=0.5,
        realized_pnl=7.0,
        status="closed",
        closed_at=datetime.now(timezone.utc),
    )
    session.add_all([old_closed, recent_closed])
    await session.commit()

    snap = await snapshot_bankroll(session, mode="paper")
    assert snap.settled_trades_total == 2
    assert snap.settled_trades_30d == 1


@pytest.mark.asyncio
async def test_snapshot_persists(session):
    await snapshot_bankroll(session, mode="paper")
    rows = (await session.execute(select(BankrollSnapshot))).scalars().all()
    assert len(rows) == 1
