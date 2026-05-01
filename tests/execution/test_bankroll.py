"""W2.2(b) — bankroll snapshot writer tests."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from uuid import uuid4

import pytest
from sqlalchemy import select

from sigil.config import config
from sigil.execution.bankroll import mark_to_market, snapshot_bankroll
from sigil.models import BankrollSnapshot, MarketPrice, Position


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


@pytest.mark.asyncio
async def test_mark_to_market_recomputes_unrealized_from_latest_price(
    session, sample_market
):
    """Open position + a fresh MarketPrice row → snapshot's
    unrealized_pnl_total must equal qty * (mid - avg_entry), and the per-row
    Position.unrealized_pnl must match what the snapshot reports."""
    now = datetime.now(timezone.utc)
    session.add(
        MarketPrice(
            time=now,
            market_id=sample_market.id,
            bid=0.58,
            ask=0.62,
            last_price=0.60,
            source="kalshi",
        )
    )
    pos = Position(
        id=uuid4(),
        platform="kalshi",
        market_id=sample_market.id,
        mode="paper",
        outcome="yes",
        quantity=100,
        avg_entry_price=0.50,
        status="open",
    )
    session.add(pos)
    await session.commit()

    n_marked = await mark_to_market(session, "paper")
    assert n_marked == 1
    await session.flush()
    await session.refresh(pos)
    # mid = 0.60, qty = 100, avg = 0.50 → unrealized = 100 * 0.10 = 10.0
    assert float(pos.current_price) == pytest.approx(0.60)
    assert float(pos.unrealized_pnl) == pytest.approx(10.0)


@pytest.mark.asyncio
async def test_snapshot_marks_to_market_so_views_agree(session, sample_market):
    """Regression for the bug that produced different unrealized values in
    /api/positions vs /api/portfolio: after snapshot_bankroll runs, the
    snapshot total must equal the sum of per-Position unrealized_pnl."""
    now = datetime.now(timezone.utc)
    session.add(
        MarketPrice(
            time=now,
            market_id=sample_market.id,
            bid=0.40,
            ask=0.44,  # mid 0.42
            last_price=0.42,
            source="kalshi",
        )
    )
    pos = Position(
        id=uuid4(),
        platform="kalshi",
        market_id=sample_market.id,
        mode="paper",
        outcome="yes",
        quantity=200,
        avg_entry_price=0.50,  # entered at 0.50, mid now 0.42 → -16.0
        status="open",
    )
    session.add(pos)
    await session.commit()

    snap = await snapshot_bankroll(session, mode="paper")
    await session.refresh(pos)
    assert float(pos.unrealized_pnl) == pytest.approx(-16.0)
    assert snap.unrealized_pnl_total == pytest.approx(float(pos.unrealized_pnl))


@pytest.mark.asyncio
async def test_mark_to_market_no_price_leaves_position_alone(
    session, sample_market
):
    """No MarketPrice row → don't overwrite stale unrealized with zero."""
    pos = Position(
        id=uuid4(),
        platform="kalshi",
        market_id=sample_market.id,
        mode="paper",
        outcome="yes",
        quantity=10,
        avg_entry_price=0.40,
        unrealized_pnl=7.5,
        status="open",
    )
    session.add(pos)
    await session.commit()

    n_marked = await mark_to_market(session, "paper")
    assert n_marked == 0
    await session.flush()
    await session.refresh(pos)
    assert float(pos.unrealized_pnl) == pytest.approx(7.5)


@pytest.mark.asyncio
async def test_mark_to_market_inverts_for_no_outcome(session, sample_market):
    """NO contracts price as 1 - YES_price."""
    now = datetime.now(timezone.utc)
    session.add(
        MarketPrice(
            time=now,
            market_id=sample_market.id,
            bid=0.70,
            ask=0.72,  # YES mid 0.71 → NO mid 0.29
            source="kalshi",
        )
    )
    pos = Position(
        id=uuid4(),
        platform="kalshi",
        market_id=sample_market.id,
        mode="paper",
        outcome="no",
        quantity=50,
        avg_entry_price=0.30,
        status="open",
    )
    session.add(pos)
    await session.commit()

    await mark_to_market(session, "paper")
    await session.flush()
    await session.refresh(pos)
    assert float(pos.current_price) == pytest.approx(0.29)
    assert float(pos.unrealized_pnl) == pytest.approx(50 * (0.29 - 0.30))
