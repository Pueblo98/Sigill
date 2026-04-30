"""Tests for the market_list widget."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from sigil.dashboard.widgets.market_list import (
    MarketListConfig,
    MarketListWidget,
)
from sigil.models import Market, MarketPrice, Prediction


def _make_widget(**kwargs) -> MarketListWidget:
    cfg = MarketListConfig(type="market_list", cache="1m", **kwargs)
    return MarketListWidget(cfg)


@pytest.mark.asyncio
async def test_empty_state(session):
    w = _make_widget()
    data = await w.fetch(session)
    assert data == []
    out = w.render(data)
    assert "No open markets" in out


@pytest.mark.asyncio
async def test_filters_status_open(session):
    session.add_all(
        [
            Market(
                platform="kalshi",
                external_id="OPEN-1",
                title="Open M",
                taxonomy_l1="x",
                status="open",
            ),
            Market(
                platform="kalshi",
                external_id="CLOSED-1",
                title="Closed M",
                taxonomy_l1="x",
                status="closed",
            ),
        ]
    )
    await session.commit()

    w = _make_widget()
    data = await w.fetch(session)
    titles = [r.title for r in data]
    assert titles == ["Open M"]


@pytest.mark.asyncio
async def test_filter_by_platform(session):
    session.add_all(
        [
            Market(
                platform="kalshi",
                external_id="K-1",
                title="K market",
                taxonomy_l1="x",
                status="open",
            ),
            Market(
                platform="polymarket",
                external_id="P-1",
                title="P market",
                taxonomy_l1="x",
                status="open",
            ),
        ]
    )
    await session.commit()

    w = _make_widget(platform="kalshi")
    data = await w.fetch(session)
    assert {r.platform for r in data} == {"kalshi"}


@pytest.mark.asyncio
async def test_join_with_latest_price(session):
    m = Market(
        platform="kalshi",
        external_id="JOIN-1",
        title="Join M",
        taxonomy_l1="x",
        status="open",
    )
    session.add(m)
    await session.commit()
    await session.refresh(m)

    now = datetime.now(timezone.utc)
    session.add_all(
        [
            MarketPrice(
                time=now - timedelta(minutes=5),
                market_id=m.id,
                bid=0.40,
                ask=0.42,
                last_price=0.41,
                volume_24h=500.0,
                source="kalshi",
            ),
            MarketPrice(
                time=now,
                market_id=m.id,
                bid=0.45,
                ask=0.47,
                last_price=0.46,
                volume_24h=1000.0,
                source="kalshi",
            ),
        ]
    )
    await session.commit()

    w = _make_widget()
    data = await w.fetch(session)
    assert len(data) == 1
    row = data[0]
    # latest price.
    assert row.bid == 0.45
    assert row.last_price == 0.46
    assert row.volume_24h == 1000.0


@pytest.mark.asyncio
async def test_min_edge_filter_uses_latest_prediction(session):
    m1 = Market(
        platform="kalshi", external_id="E-1", title="High edge",
        taxonomy_l1="x", status="open",
    )
    m2 = Market(
        platform="kalshi", external_id="E-2", title="Low edge",
        taxonomy_l1="x", status="open",
    )
    m3 = Market(
        platform="kalshi", external_id="E-3", title="No prediction",
        taxonomy_l1="x", status="open",
    )
    session.add_all([m1, m2, m3])
    await session.commit()
    await session.refresh(m1)
    await session.refresh(m2)

    now = datetime.now(timezone.utc)
    session.add_all(
        [
            Prediction(
                market_id=m1.id, model_id="a", model_version="1",
                predicted_prob=0.6, edge=0.10, created_at=now,
            ),
            Prediction(
                market_id=m2.id, model_id="a", model_version="1",
                predicted_prob=0.6, edge=0.01, created_at=now,
            ),
        ]
    )
    await session.commit()

    w = _make_widget(min_edge=0.05)
    data = await w.fetch(session)
    titles = [r.title for r in data]
    assert "High edge" in titles
    assert "Low edge" not in titles
    assert "No prediction" not in titles


@pytest.mark.asyncio
async def test_sort_volume_desc(session):
    m1 = Market(
        platform="kalshi", external_id="V-1", title="Low vol",
        taxonomy_l1="x", status="open",
    )
    m2 = Market(
        platform="kalshi", external_id="V-2", title="High vol",
        taxonomy_l1="x", status="open",
    )
    session.add_all([m1, m2])
    await session.commit()
    await session.refresh(m1)
    await session.refresh(m2)

    now = datetime.now(timezone.utc)
    session.add_all(
        [
            MarketPrice(
                time=now, market_id=m1.id, last_price=0.5,
                volume_24h=10.0, source="kalshi",
            ),
            MarketPrice(
                time=now, market_id=m2.id, last_price=0.5,
                volume_24h=5000.0, source="kalshi",
            ),
        ]
    )
    await session.commit()

    w = _make_widget(sort="volume_desc")
    data = await w.fetch(session)
    assert data[0].title == "High vol"
    assert data[1].title == "Low vol"


@pytest.mark.asyncio
async def test_render_handles_null_price_fields(session):
    m = Market(
        platform="kalshi", external_id="N-1", title="Null fields",
        taxonomy_l1="x", status="open",
    )
    session.add(m)
    await session.commit()

    w = _make_widget()
    data = await w.fetch(session)
    out = w.render(data)
    assert "Null fields" in out
    # Null bid/ask/last/volume render as "-"
    assert "<td>-</td>" in out
