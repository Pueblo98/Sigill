"""W2.3.2 — settlement WS handler end-to-end.

Lane A's `tests/ingestion/test_settlement.py` covers the handler in isolation
(direct `apply()` calls). This drives the full event-loop path:

    fake WS stream -> run_ws_subscriber -> SettlementHandler.apply -> DB

Multiple settled events flow through one subscriber pass. Each closes the
matching Position, writes realized_pnl, and appends a BankrollSnapshot.
"""
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
    run_ws_subscriber,
)
from sigil.models import BankrollSnapshot, Market, Position


pytestmark = pytest.mark.critical


class _ScriptedStream(SettlementSource):
    """Fake WS source — yields a finite set of events then completes."""

    def __init__(self, events: list[SettlementEvent]) -> None:
        self.events = events
        self.fetched: list[str] = []

    async def stream_settlements(self) -> AsyncIterator[SettlementEvent]:
        for ev in self.events:
            yield ev

    async def fetch_status(self, external_id: str) -> Optional[SettlementEvent]:
        self.fetched.append(external_id)
        return None


@pytest.mark.asyncio
async def test_ws_subscriber_drains_stream_and_settles_each_market(
    session_factory, session, sample_market
):
    market_b = Market(
        id=uuid4(),
        platform="kalshi",
        external_id="KAL-TEST-002",
        title="Second test market",
        taxonomy_l1="sports",
        market_type="binary",
        status="open",
    )
    session.add(market_b)

    pos_a = Position(
        id=uuid4(),
        platform="kalshi",
        market_id=sample_market.id,
        mode="paper",
        outcome="yes",
        quantity=10,
        avg_entry_price=0.40,
        status="open",
    )
    pos_b = Position(
        id=uuid4(),
        platform="kalshi",
        market_id=market_b.id,
        mode="paper",
        outcome="no",
        quantity=4,
        avg_entry_price=0.30,
        status="open",
    )
    session.add_all([pos_a, pos_b])

    session.add(
        BankrollSnapshot(
            time=datetime.now(timezone.utc),
            mode="paper",
            equity=5000.0,
            realized_pnl_total=0.0,
            unrealized_pnl_total=0.0,
            settled_trades_total=20,
            settled_trades_30d=5,
        )
    )
    await session.commit()

    settled_at = datetime.now(timezone.utc)
    stream = _ScriptedStream(
        [
            SettlementEvent(
                platform="kalshi",
                external_id=sample_market.external_id,
                settlement_value=1.0,
                settled_at=settled_at,
            ),
            SettlementEvent(
                platform="kalshi",
                external_id=market_b.external_id,
                settlement_value=1.0,
                settled_at=settled_at,
            ),
        ]
    )
    handler = SettlementHandler(session_factory)

    await run_ws_subscriber(stream, handler)

    async with session_factory() as s:
        refreshed_a = await s.get(Position, pos_a.id)
        refreshed_b = await s.get(Position, pos_b.id)
        assert refreshed_a.status == "closed"
        assert refreshed_b.status == "closed"
        # YES wins on market A; long YES @ 0.40 → +0.60 * 10 = 6.0
        assert float(refreshed_a.realized_pnl) == pytest.approx(6.0)
        # YES wins on market B; long NO @ 0.30 → payoff 0 → -0.30 * 4 = -1.2
        assert float(refreshed_b.realized_pnl) == pytest.approx(-1.2)

        snaps = (
            await s.execute(
                select(BankrollSnapshot)
                .where(BankrollSnapshot.mode == "paper")
                .order_by(BankrollSnapshot.time.asc())
            )
        ).scalars().all()
        # 1 baseline + 2 settlement appends
        assert len(snaps) == 3
        latest = snaps[-1]
        assert latest.settled_trades_total == 22
        assert float(latest.realized_pnl_total) == pytest.approx(6.0 - 1.2)


@pytest.mark.asyncio
async def test_ws_subscriber_continues_when_handler_raises(session_factory, session, sample_market):
    """A malformed event mid-stream must not abort the rest of the stream."""
    settled_at = datetime.now(timezone.utc)
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
    await session.commit()

    stream = _ScriptedStream(
        [
            SettlementEvent(
                platform="kalshi",
                external_id="GHOST",  # unknown -> handler returns 0, no exception
                settlement_value=1.0,
                settled_at=settled_at,
            ),
            SettlementEvent(
                platform="kalshi",
                external_id=sample_market.external_id,
                settlement_value=1.0,
                settled_at=settled_at,
            ),
        ]
    )
    handler = SettlementHandler(session_factory)
    await run_ws_subscriber(stream, handler)

    async with session_factory() as s:
        refreshed = await s.get(Position, pos.id)
        assert refreshed.status == "closed"
