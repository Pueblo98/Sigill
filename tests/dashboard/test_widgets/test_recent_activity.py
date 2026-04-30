"""Tests for the recent_activity widget."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from uuid import uuid4

import pytest

from sigil.dashboard.widgets.recent_activity import (
    RecentActivityConfig,
    RecentActivityWidget,
)
from sigil.models import Order, Position


def _make_widget(limit: int = 20) -> RecentActivityWidget:
    return RecentActivityWidget(
        RecentActivityConfig(type="recent_activity", cache="30s", limit=limit)
    )


@pytest.mark.asyncio
async def test_empty_state(session):
    w = _make_widget()
    data = await w.fetch(session)
    assert data == []
    out = w.render(data)
    assert "No recent activity." in out


@pytest.mark.asyncio
async def test_combined_feed_sorted_desc(session, sample_market):
    now = datetime.now(timezone.utc)
    session.add_all(
        [
            Order(
                client_order_id=f"sigil_{uuid4()}",
                platform="kalshi",
                market_id=sample_market.id,
                mode="paper",
                side="buy",
                outcome="yes",
                order_type="limit",
                price=0.50,
                quantity=10,
                created_at=now - timedelta(minutes=10),
            ),
            Order(
                client_order_id=f"sigil_{uuid4()}",
                platform="kalshi",
                market_id=sample_market.id,
                mode="paper",
                side="sell",
                outcome="no",
                order_type="market",
                price=0.55,
                quantity=5,
                created_at=now - timedelta(minutes=2),
            ),
            Position(
                platform="kalshi",
                market_id=sample_market.id,
                mode="paper",
                outcome="yes",
                quantity=20,
                avg_entry_price=0.45,
                realized_pnl=12.50,
                status="closed",
                opened_at=now - timedelta(hours=2),
                closed_at=now - timedelta(minutes=5),
            ),
            Position(
                platform="kalshi",
                market_id=sample_market.id,
                mode="paper",
                outcome="no",
                quantity=10,
                avg_entry_price=0.55,
                realized_pnl=-5.0,
                status="settled",
                opened_at=now - timedelta(hours=1),
                closed_at=now - timedelta(minutes=1),
            ),
        ]
    )
    await session.commit()

    w = _make_widget()
    data = await w.fetch(session)
    assert len(data) == 4
    # Sorted DESC by `when`.
    for a, b in zip(data, data[1:]):
        assert a.when >= b.when

    actions = [e.action for e in data]
    assert "settlement" in actions
    assert "position closed" in actions
    assert "order placed" in actions


@pytest.mark.asyncio
async def test_limit_caps_results(session, sample_market):
    now = datetime.now(timezone.utc)
    for i in range(10):
        session.add(
            Order(
                client_order_id=f"sigil_{uuid4()}",
                platform="kalshi",
                market_id=sample_market.id,
                mode="paper",
                side="buy",
                outcome="yes",
                order_type="limit",
                price=0.50,
                quantity=1,
                created_at=now - timedelta(minutes=i),
            )
        )
    await session.commit()

    w = _make_widget(limit=4)
    data = await w.fetch(session)
    assert len(data) == 4


@pytest.mark.asyncio
async def test_skips_open_positions(session, sample_market):
    now = datetime.now(timezone.utc)
    session.add(
        Position(
            platform="kalshi",
            market_id=sample_market.id,
            mode="paper",
            outcome="yes",
            quantity=10,
            avg_entry_price=0.50,
            status="open",
            opened_at=now,
        )
    )
    await session.commit()

    w = _make_widget()
    data = await w.fetch(session)
    assert data == []
