"""Settlement: WS settled event closes positions; poll fallback catches misses."""
from __future__ import annotations

from datetime import datetime, timezone
from typing import AsyncIterator, Optional
from uuid import uuid4

import pytest
from sqlalchemy import select

from sigil.ingestion.settlement import (
    SettlementEvent,
    SettlementHandler,
    SettlementSource,
    poll_once,
)
from sigil.models import BankrollSnapshot, Market, Position


class FakeSettlementSource(SettlementSource):
    def __init__(self, events: list[SettlementEvent], statuses: dict[str, SettlementEvent] | None = None):
        self.events = events
        self.statuses = statuses or {}

    async def stream_settlements(self) -> AsyncIterator[SettlementEvent]:
        for ev in self.events:
            yield ev

    async def fetch_status(self, external_id: str) -> Optional[SettlementEvent]:
        return self.statuses.get(external_id)


@pytest.mark.critical
async def test_ws_settled_event_closes_positions_and_realizes_pnl(session_factory, session, sample_market):
    pos = Position(
        id=uuid4(),
        platform="kalshi",
        market_id=sample_market.id,
        mode="paper",
        outcome="yes",
        quantity=10,
        avg_entry_price=0.40,
        status="open",
    )
    session.add(pos)
    session.add(BankrollSnapshot(
        time=datetime.now(timezone.utc),
        mode="paper",
        equity=5000.0,
        realized_pnl_total=0.0, unrealized_pnl_total=0.0,
        settled_trades_total=20, settled_trades_30d=5,
    ))
    await session.commit()

    handler = SettlementHandler(session_factory)
    event = SettlementEvent(
        platform="kalshi",
        external_id=sample_market.external_id,
        settlement_value=1.0,  # YES wins
        settled_at=datetime.now(timezone.utc),
    )
    settled = await handler.apply(event)
    assert settled == 1

    async with session_factory() as s:
        refreshed = await s.get(Position, pos.id)
        assert refreshed.status == "closed"
        assert refreshed.quantity == 0
        # YES wins, paid 0.40 per contract -> +0.60 * 10 = 6.0
        assert float(refreshed.realized_pnl) == pytest.approx(6.0)

        market = await s.get(Market, sample_market.id)
        assert market.status == "settled"
        assert float(market.settlement_value) == 1.0

        snap = (await s.execute(
            select(BankrollSnapshot).where(BankrollSnapshot.mode == "paper").order_by(BankrollSnapshot.time.desc())
        )).scalars().first()
        assert float(snap.realized_pnl_total) == pytest.approx(6.0)
        assert snap.settled_trades_total == 21


@pytest.mark.critical
async def test_no_outcome_pays_correctly(session_factory, session, sample_market):
    pos = Position(
        id=uuid4(),
        platform="kalshi",
        market_id=sample_market.id,
        mode="paper",
        outcome="no",
        quantity=10,
        avg_entry_price=0.55,
        status="open",
    )
    session.add(pos)
    await session.commit()

    handler = SettlementHandler(session_factory)
    event = SettlementEvent(
        platform="kalshi",
        external_id=sample_market.external_id,
        settlement_value=0.0,  # NO wins
        settled_at=datetime.now(timezone.utc),
    )
    await handler.apply(event)

    async with session_factory() as s:
        refreshed = await s.get(Position, pos.id)
        # NO wins, paid 0.55 -> payoff 1.0 - 0.0 = 1.0 -> +0.45 * 10 = 4.5
        assert float(refreshed.realized_pnl) == pytest.approx(4.5)


@pytest.mark.critical
async def test_poll_fallback_settles_missed_event(session_factory, session, sample_market):
    pos = Position(
        id=uuid4(),
        platform="kalshi",
        market_id=sample_market.id,
        mode="paper",
        outcome="yes",
        quantity=5,
        avg_entry_price=0.50,
        status="open",
    )
    session.add(pos)
    await session.commit()

    source = FakeSettlementSource(
        events=[],
        statuses={
            sample_market.external_id: SettlementEvent(
                platform="kalshi",
                external_id=sample_market.external_id,
                settlement_value=1.0,
                settled_at=datetime.now(timezone.utc),
            )
        },
    )
    handler = SettlementHandler(session_factory)
    settled = await poll_once(source, handler, session_factory)
    assert settled == 1
    async with session_factory() as s:
        refreshed = await s.get(Position, pos.id)
        assert refreshed.status == "closed"


async def test_settlement_for_unknown_market_is_noop(session_factory):
    handler = SettlementHandler(session_factory)
    event = SettlementEvent(
        platform="kalshi", external_id="GHOST", settlement_value=1.0,
        settled_at=datetime.now(timezone.utc),
    )
    settled = await handler.apply(event)
    assert settled == 0
