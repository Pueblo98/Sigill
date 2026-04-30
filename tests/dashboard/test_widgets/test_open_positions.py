"""Tests for the open_positions widget."""

from __future__ import annotations

from datetime import datetime, timezone

import pytest

from sigil.dashboard.widgets.open_positions import (
    OpenPositionsConfig,
    OpenPositionsWidget,
)
from sigil.models import Position


def _make_widget(mode: str = "paper") -> OpenPositionsWidget:
    return OpenPositionsWidget(
        OpenPositionsConfig(type="open_positions", cache="1m", mode=mode)
    )


@pytest.mark.asyncio
async def test_empty_state(session):
    w = _make_widget()
    data = await w.fetch(session)
    assert data == []
    out = w.render(data)
    assert "No open positions." in out


@pytest.mark.asyncio
async def test_returns_open_only(session, sample_market):
    now = datetime.now(timezone.utc)
    session.add_all(
        [
            Position(
                platform="kalshi",
                market_id=sample_market.id,
                mode="paper",
                outcome="yes",
                quantity=100,
                avg_entry_price=0.50,
                current_price=0.55,
                unrealized_pnl=5.0,
                status="open",
                opened_at=now,
            ),
            Position(
                platform="kalshi",
                market_id=sample_market.id,
                mode="paper",
                outcome="no",
                quantity=50,
                avg_entry_price=0.40,
                status="closed",
                opened_at=now,
            ),
        ]
    )
    await session.commit()

    w = _make_widget()
    data = await w.fetch(session)
    assert len(data) == 1
    assert data[0].outcome == "yes"
    assert data[0].unrealized_pnl == 5.0


@pytest.mark.asyncio
async def test_filters_by_mode(session, sample_market):
    now = datetime.now(timezone.utc)
    session.add_all(
        [
            Position(
                platform="kalshi",
                market_id=sample_market.id,
                mode="paper",
                outcome="yes",
                quantity=10,
                avg_entry_price=0.50,
                status="open",
                opened_at=now,
            ),
            Position(
                platform="kalshi",
                market_id=sample_market.id,
                mode="live",
                outcome="no",
                quantity=20,
                avg_entry_price=0.60,
                status="open",
                opened_at=now,
            ),
        ]
    )
    await session.commit()

    w = _make_widget(mode="live")
    data = await w.fetch(session)
    assert len(data) == 1
    assert data[0].outcome == "no"


@pytest.mark.asyncio
async def test_render_handles_null_current_price(session, sample_market):
    now = datetime.now(timezone.utc)
    session.add(
        Position(
            platform="kalshi",
            market_id=sample_market.id,
            mode="paper",
            outcome="yes",
            quantity=10,
            avg_entry_price=0.50,
            current_price=None,
            unrealized_pnl=None,
            status="open",
            opened_at=now,
        )
    )
    await session.commit()

    w = _make_widget()
    data = await w.fetch(session)
    out = w.render(data)
    assert sample_market.title in out
    # Null current_price renders as "-"
    assert "<td>-</td>" in out
