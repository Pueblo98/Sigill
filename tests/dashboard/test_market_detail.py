"""Market detail page — view builder for /market/{external_id}.

We test the context builder (pure async, no HTTP) — the route in
``mount.py`` is a thin wrapper around it. A previous iteration also
hit the route via ``TestClient`` but Windows asyncio's proactor
transport is flaky under full-suite load (intermittent
``proactor_events.py: 'NoneType' object has no attribute 'send'``);
the view tests below cover the same logic deterministically.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from uuid import uuid4

import pytest

from sigil.dashboard.views.market_detail import build_context
from sigil.models import (
    Market,
    MarketPrice,
    Order,
    Position,
    Prediction,
    PredictionFeature,
)


async def _seed(session, *, ext_id="KX-DETAIL", platform="kalshi", taxonomy="sports"):
    market = Market(
        id=uuid4(),
        platform=platform,
        external_id=ext_id,
        title=f"Will {ext_id} happen?",
        taxonomy_l1=taxonomy,
        market_type="binary",
        status="open",
    )
    session.add(market)
    session.add(MarketPrice(
        time=datetime.now(timezone.utc),
        market_id=market.id,
        bid=0.42, ask=0.44, last_price=0.43,
        volume_24h=12345.0, source="test",
    ))
    pred = Prediction(
        id=uuid4(),
        market_id=market.id,
        model_id="spread_arb",
        model_version="v0",
        predicted_prob=0.55, confidence=0.85,
        market_price_at_prediction=0.43, edge=0.12,
    )
    session.add(pred)
    for name, value in (
        ("polymarket_yes_price", 0.55),
        ("kalshi_yes_price", 0.43),
        ("match_score", 96.0),
    ):
        session.add(PredictionFeature(
            prediction_id=pred.id, feature_name=name, value=value, version=1,
        ))
    session.add(Order(
        id=uuid4(), client_order_id=f"test_{ext_id}",
        platform=platform, market_id=market.id, prediction_id=pred.id,
        mode="paper", side="buy", outcome="yes", order_type="limit",
        price=0.43, quantity=100, filled_quantity=100, avg_fill_price=0.43,
        status="filled",
    ))
    session.add(Position(
        id=uuid4(), platform=platform, market_id=market.id,
        mode="paper", outcome="yes", quantity=100,
        avg_entry_price=0.43, current_price=0.50, unrealized_pnl=7.0,
        status="open",
    ))
    await session.commit()
    return market


# ---------- view-builder tests (no HTTP) ---------- #


async def test_build_context_returns_none_for_missing_market(session):
    ctx = await build_context(session, "DOES-NOT-EXIST")
    assert ctx is None


async def test_build_context_breadcrumb_for_kalshi_ticker(session):
    """Kalshi multi-segment tickers should produce series + event."""
    market = await _seed(session, ext_id="KXNBAGAME-26MAY01CLETOR-CLE")
    ctx = await build_context(session, market.external_id)
    assert ctx is not None
    assert ctx.breadcrumb.series == "KXNBAGAME"
    assert ctx.breadcrumb.event == "KXNBAGAME-26MAY01CLETOR"
    assert ctx.breadcrumb.ticker == "KXNBAGAME-26MAY01CLETOR-CLE"


async def test_build_context_breadcrumb_polymarket_no_structure(session):
    market = await _seed(session, ext_id="0xABC123", platform="polymarket")
    ctx = await build_context(session, market.external_id)
    assert ctx is not None
    assert ctx.breadcrumb.series is None
    assert ctx.breadcrumb.event is None
    assert ctx.breadcrumb.ticker == "0xABC123"


async def test_build_context_loads_predictions_with_features(session):
    market = await _seed(session)
    ctx = await build_context(session, market.external_id)
    assert ctx is not None
    assert ctx.market.external_id == market.external_id
    assert len(ctx.predictions) == 1
    p = ctx.predictions[0]
    feature_names = {f["name"] for f in p.features}
    assert feature_names == {"polymarket_yes_price", "kalshi_yes_price", "match_score"}
    assert ctx.latest_prediction is not None
    assert ctx.latest_prediction.edge == pytest.approx(0.12)


async def test_build_context_loads_lifecycle_entries(session):
    market = await _seed(session)
    ctx = await build_context(session, market.external_id)
    assert ctx is not None
    kinds = {e.kind for e in ctx.lifecycle}
    assert kinds == {"order", "position"}
    # Open positions don't add a "closed" entry.
    actions = [e.action for e in ctx.lifecycle]
    assert any(a == "position opened" for a in actions)
    assert not any("closed" in a for a in actions)


async def test_build_context_siblings_event_for_kalshi_prefix(session):
    # Three NBA-game-style tickers under same event prefix.
    primary = await _seed(session, ext_id="KXNBAGAME-26MAY01CLETOR-CLE")
    await _seed(session, ext_id="KXNBAGAME-26MAY01CLETOR-TOR", taxonomy="sports")
    await _seed(session, ext_id="KXNBAGAME-26MAY01CLETOR-DRAW", taxonomy="sports")
    # And one unrelated.
    await _seed(session, ext_id="KXFEDDEC-DEC25-CUT", taxonomy="economics")

    ctx = await build_context(session, primary.external_id)
    assert ctx is not None
    sibling_ids = {s.external_id for s in ctx.siblings_event}
    assert "KXNBAGAME-26MAY01CLETOR-TOR" in sibling_ids
    assert "KXNBAGAME-26MAY01CLETOR-DRAW" in sibling_ids
    assert "KXFEDDEC-DEC25-CUT" not in sibling_ids


async def test_build_context_siblings_taxonomy_excludes_self(session):
    primary = await _seed(session, ext_id="KX-A", taxonomy="sports")
    await _seed(session, ext_id="KX-B", taxonomy="sports")
    await _seed(session, ext_id="KX-C", taxonomy="sports")
    await _seed(session, ext_id="KX-D", taxonomy="economics")  # different tax

    ctx = await build_context(session, primary.external_id)
    assert ctx is not None
    tax_ids = {s.external_id for s in ctx.siblings_taxonomy}
    assert "KX-A" not in tax_ids
    assert "KX-B" in tax_ids
    assert "KX-C" in tax_ids
    assert "KX-D" not in tax_ids


