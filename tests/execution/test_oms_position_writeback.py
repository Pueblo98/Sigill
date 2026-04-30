"""TODO-4: OMS opens/updates a Position row on fill.

Surfaced during W2.4 smoke test — paper-mode orders FILLED but no Position
landed, so settlement and reconciliation had nothing to operate on.
"""
from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

import pytest
from sqlalchemy import select

from sigil.execution.oms import OMS, OrderState
from sigil.models import MarketPrice, Position


pytestmark = pytest.mark.critical


@pytest.mark.asyncio
async def test_paper_fill_opens_position(session, sample_market):
    session.add(
        MarketPrice(
            time=datetime.now(timezone.utc),
            market_id=sample_market.id,
            bid=0.41,
            ask=0.43,
            last_price=0.42,
            source="test",
        )
    )
    await session.commit()

    oms = OMS(session=session)
    order = await oms.create(
        platform="kalshi",
        market_id=sample_market.id,
        side="buy",
        outcome="yes",
        price=0.50,
        quantity=10,
        order_type="limit",
        mode="paper",
    )
    await session.commit()
    await oms.submit(order, sample_market.external_id)
    await session.commit()

    rows = (
        await session.execute(
            select(Position).where(Position.market_id == sample_market.id)
        )
    ).scalars().all()
    assert len(rows) == 1
    pos = rows[0]
    assert pos.status == "open"
    assert pos.quantity == 10
    assert pos.outcome == "yes"
    assert pos.mode == "paper"
    # Filled at ask (0.43 from MarketPrice)
    assert float(pos.avg_entry_price) == pytest.approx(0.43)


@pytest.mark.asyncio
async def test_second_buy_fill_updates_avg_entry_price(session, sample_market):
    session.add(
        MarketPrice(
            time=datetime.now(timezone.utc),
            market_id=sample_market.id,
            bid=0.39,
            ask=0.40,
            last_price=0.40,
            source="test",
        )
    )
    await session.commit()

    oms = OMS(session=session)
    o1 = await oms.create(
        platform="kalshi",
        market_id=sample_market.id,
        side="buy",
        outcome="yes",
        price=0.40,
        quantity=10,
        order_type="limit",
        mode="paper",
    )
    await session.commit()
    await oms.submit(o1, sample_market.external_id)
    await session.commit()

    # second fill at a higher price; avg should weight by quantity
    session.add(
        MarketPrice(
            time=datetime.now(timezone.utc),
            market_id=sample_market.id,
            bid=0.49,
            ask=0.50,
            last_price=0.50,
            source="test",
        )
    )
    await session.commit()

    o2 = await oms.create(
        platform="kalshi",
        market_id=sample_market.id,
        side="buy",
        outcome="yes",
        price=0.50,
        quantity=10,
        order_type="limit",
        mode="paper",
    )
    await session.commit()
    await oms.submit(o2, sample_market.external_id)
    await session.commit()

    rows = (
        await session.execute(
            select(Position).where(Position.market_id == sample_market.id, Position.status == "open")
        )
    ).scalars().all()
    assert len(rows) == 1
    pos = rows[0]
    assert pos.quantity == 20
    # (10 * 0.40 + 10 * 0.50) / 20 = 0.45
    assert float(pos.avg_entry_price) == pytest.approx(0.45)


@pytest.mark.asyncio
async def test_paper_and_live_modes_get_separate_positions(session, sample_market):
    """The Position uniqueness key is (platform, market_id, outcome, mode);
    paper and live must not collide."""
    oms = OMS(session=session)

    paper = await oms.create(
        platform="kalshi",
        market_id=sample_market.id,
        side="buy",
        outcome="yes",
        price=0.42,
        quantity=5,
        order_type="limit",
        mode="paper",
    )
    await session.commit()
    await oms.submit(paper, sample_market.external_id)
    await session.commit()

    rows = (
        await session.execute(
            select(Position).where(Position.market_id == sample_market.id)
        )
    ).scalars().all()
    assert len(rows) == 1
    assert rows[0].mode == "paper"


@pytest.mark.asyncio
async def test_live_fill_opens_position(session, sample_market):
    class _Adapter:
        async def place_order(self, **kwargs):
            return {
                "external_order_id": "ext_xyz",
                "status": "filled",
                "filled_quantity": kwargs["quantity"],
                "avg_fill_price": kwargs["price"],
                "fees": 0.0,
            }

    oms = OMS(session=session, adapter=_Adapter(), max_submit_retries=1)
    order = await oms.create(
        platform="kalshi",
        market_id=sample_market.id,
        side="buy",
        outcome="yes",
        price=0.42,
        quantity=10,
        order_type="limit",
        mode="live",
    )
    await session.commit()
    await oms.submit(order, sample_market.external_id)
    await session.commit()

    pos = (
        await session.execute(
            select(Position).where(Position.market_id == sample_market.id, Position.mode == "live")
        )
    ).scalar_one()
    assert pos.quantity == 10
    assert pos.status == "open"
    assert order.status == OrderState.FILLED


@pytest.mark.asyncio
async def test_live_pending_status_does_not_open_position(session, sample_market):
    """When the exchange returns pending_on_exchange (not filled), the position
    must wait for the actual fill before being opened."""

    class _Adapter:
        async def place_order(self, **kwargs):
            return {
                "external_order_id": "ext_pending",
                "status": "pending_on_exchange",
                "filled_quantity": 0,
                "avg_fill_price": None,
                "fees": 0.0,
            }

    oms = OMS(session=session, adapter=_Adapter(), max_submit_retries=1)
    order = await oms.create(
        platform="kalshi",
        market_id=sample_market.id,
        side="buy",
        outcome="yes",
        price=0.42,
        quantity=10,
        order_type="limit",
        mode="live",
    )
    await session.commit()
    await oms.submit(order, sample_market.external_id)
    await session.commit()

    rows = (await session.execute(select(Position))).scalars().all()
    assert rows == []


@pytest.mark.asyncio
async def test_sell_fill_against_open_position_reduces_qty_and_realizes_pnl(session, sample_market):
    open_pos = Position(
        id=uuid4(),
        platform="kalshi",
        market_id=sample_market.id,
        mode="paper",
        outcome="yes",
        quantity=10,
        avg_entry_price=0.40,
        status="open",
    )
    session.add(open_pos)
    session.add(
        MarketPrice(
            time=datetime.now(timezone.utc),
            market_id=sample_market.id,
            bid=0.59,
            ask=0.60,
            last_price=0.60,
            source="test",
        )
    )
    await session.commit()

    oms = OMS(session=session)
    sell = await oms.create(
        platform="kalshi",
        market_id=sample_market.id,
        side="sell",
        outcome="yes",
        price=0.60,
        quantity=4,
        order_type="limit",
        mode="paper",
    )
    await session.commit()
    await oms.submit(sell, sample_market.external_id)
    await session.commit()

    refreshed = await session.get(Position, open_pos.id)
    assert refreshed.quantity == 6
    # Sell fills at bid (0.59) on paper. Realized = 4 * (0.59 - 0.40) = 0.76
    assert float(refreshed.realized_pnl) == pytest.approx(0.76)
    assert refreshed.status == "open"


@pytest.mark.asyncio
async def test_sell_with_no_open_position_logs_and_skips(session, sample_market, caplog):
    oms = OMS(session=session)
    order = await oms.create(
        platform="kalshi",
        market_id=sample_market.id,
        side="sell",
        outcome="yes",
        price=0.60,
        quantity=5,
        order_type="limit",
        mode="paper",
    )
    await session.commit()
    with caplog.at_level("WARNING"):
        await oms.submit(order, sample_market.external_id)
    await session.commit()

    rows = (await session.execute(select(Position))).scalars().all()
    assert rows == []
    assert any("no open position" in r.message.lower() for r in caplog.records)
