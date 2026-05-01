"""market_list widget v2 — drops Edge, adds Category + per-row link."""
from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

import pytest
from sqlalchemy import select

from sigil.dashboard.widgets.market_list import (
    MarketListConfig,
    MarketListWidget,
    MarketRow,
)
from sigil.models import Market, MarketPrice


def _widget(**overrides):
    cfg = MarketListConfig(type="market_list", cache="1m", **overrides)
    return MarketListWidget(cfg)


async def test_fetch_returns_taxonomy_and_no_edge(session):
    market = Market(
        id=uuid4(), platform="kalshi", external_id="KX-TAX",
        title="Test market", taxonomy_l1="economics",
        market_type="binary", status="open",
    )
    session.add(market)
    session.add(MarketPrice(
        time=datetime.now(timezone.utc),
        market_id=market.id, last_price=0.5, volume_24h=999.0, source="t",
    ))
    await session.commit()

    rows = await _widget().fetch(session=session)
    assert len(rows) == 1
    assert rows[0].taxonomy_l1 == "economics"
    # MarketRow must not have an `edge` attribute anymore.
    assert not hasattr(rows[0], "edge")


def test_render_drops_edge_column():
    out = str(_widget().render([
        MarketRow(
            market_id="x", external_id="KX-1", platform="kalshi",
            title="T", taxonomy_l1="sports",
            bid=0.4, ask=0.5, last_price=0.45, volume_24h=1234.0,
            last_price_at=None,
        )
    ]))
    assert "<th>Category</th>" in out
    assert "<th>Edge</th>" not in out


def test_render_wraps_title_in_link():
    out = str(_widget().render([
        MarketRow(
            market_id="x", external_id="KX-LINK-ME", platform="kalshi",
            title="Linked title", taxonomy_l1="general",
            bid=None, ask=None, last_price=None, volume_24h=None,
            last_price_at=None,
        )
    ]))
    assert '<a href="/market/KX-LINK-ME">Linked title</a>' in out


def test_render_empty_state_unchanged():
    out = str(_widget().render([]))
    assert "No open markets" in out


def test_legacy_min_edge_filter_is_silently_dropped():
    # Older YAML still passes filters: { min_edge: ... }; the model
    # validator should accept and ignore.
    cfg = MarketListConfig(
        type="market_list", cache="1m",
        filters={"min_edge": 0.1, "platform": "kalshi"},
    )
    assert cfg.platform == "kalshi"
    # min_edge is no longer a field
    assert not hasattr(cfg, "min_edge")
