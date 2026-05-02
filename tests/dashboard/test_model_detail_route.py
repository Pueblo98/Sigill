"""Model detail page — view builder for /models/{model_id}.

Mirrors the test pattern in ``test_market_detail.py`` and
``test_markets_list_route.py``: exercise the context builder against an
in-memory SQLite session. The route in ``mount.py`` is a thin wrapper.
"""
from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

import pytest

# Importing this module registers the spread_arb ModelDef in the registry.
import sigil.signals.spread_arb  # noqa: F401
from sigil.dashboard.views.model_detail import build_context
from sigil.models import Market, Order, Position, Prediction


async def _seed_market(session, *, ext_id: str) -> Market:
    market = Market(
        id=uuid4(),
        platform="kalshi",
        external_id=ext_id,
        title=f"Will {ext_id}?",
        taxonomy_l1="sports",
        market_type="binary",
        status="open",
    )
    session.add(market)
    await session.commit()
    await session.refresh(market)
    return market


async def _seed_prediction(
    session, *, market: Market, model_id: str = "spread_arb", edge: float = 0.10
) -> Prediction:
    pred = Prediction(
        id=uuid4(),
        market_id=market.id,
        model_id=model_id,
        model_version="v0",
        predicted_prob=0.60,
        confidence=0.80,
        market_price_at_prediction=0.50,
        edge=edge,
    )
    session.add(pred)
    await session.commit()
    await session.refresh(pred)
    return pred


async def _seed_order_position(
    session,
    *,
    market: Market,
    prediction: Prediction,
    realized_pnl: float = 5.0,
    status: str = "closed",
) -> tuple[Order, Position]:
    order = Order(
        id=uuid4(),
        platform="kalshi",
        market_id=market.id,
        prediction_id=prediction.id,
        client_order_id=f"co-{uuid4().hex[:6]}",
        external_order_id=f"ex-{uuid4().hex[:6]}",
        mode="paper",
        side="buy",
        outcome="yes",
        order_type="limit",
        price=0.50,
        quantity=10,
        filled_quantity=10,
        avg_fill_price=0.50,
        fees=0.0,
        status="filled",
    )
    session.add(order)
    pos = Position(
        id=uuid4(),
        platform="kalshi",
        market_id=market.id,
        outcome="yes",
        mode="paper",
        quantity=10,
        avg_entry_price=0.50,
        current_price=0.55,
        realized_pnl=realized_pnl,
        unrealized_pnl=0.0,
        status=status,
        opened_at=datetime.now(timezone.utc),
        closed_at=datetime.now(timezone.utc) if status == "closed" else None,
    )
    session.add(pos)
    await session.commit()
    return order, pos


async def test_unknown_model_returns_none(session):
    ctx = await build_context(session, "no-such-model-xyz")
    assert ctx is None


async def test_known_model_with_no_data_renders_empty_view(session):
    ctx = await build_context(session, "spread_arb")
    assert ctx is not None
    assert ctx.model_id == "spread_arb"
    assert ctx.display_name == "Stat Arb (Cross-Platform)"
    assert ctx.version == "v0"
    assert "arbitrage" in ctx.tags
    # Empty registry-only state.
    assert ctx.summary["state"] == "no_data"
    assert ctx.recent_trades == []
    assert ctx.recent_predictions == []
    assert ctx.equity_curve_points == 0
    # Empty curve still produces a placeholder SVG (charts._empty_svg).
    assert "<svg" in ctx.equity_curve_svg


async def test_model_with_predictions_and_closed_position(session):
    market = await _seed_market(session, ext_id="KX-MODEL-1")
    pred = await _seed_prediction(session, market=market, edge=0.12)
    await _seed_order_position(
        session, market=market, prediction=pred, realized_pnl=7.5, status="closed"
    )

    ctx = await build_context(session, "spread_arb")
    assert ctx is not None
    assert ctx.summary["state"] == "ok"
    assert ctx.summary["trades_total"] == 1
    assert ctx.summary["realized_pnl"] == pytest.approx(7.5, rel=1e-6)
    # Equity curve: one closed position → one point.
    assert ctx.equity_curve_points == 1
    assert "<svg" in ctx.equity_curve_svg
    # Recent trades + predictions populated.
    assert len(ctx.recent_trades) == 1
    assert ctx.recent_trades[0]["external_id"] == "KX-MODEL-1"
    assert ctx.recent_trades[0]["status"] == "filled"
    assert len(ctx.recent_predictions) == 1
    assert ctx.recent_predictions[0]["external_id"] == "KX-MODEL-1"
    assert ctx.recent_predictions[0]["edge"] == pytest.approx(0.12, rel=1e-6)


async def test_predictions_for_other_model_excluded(session):
    market = await _seed_market(session, ext_id="KX-MODEL-2")
    # Both spread_arb and a hypothetical other model emit predictions on
    # the same market — only spread_arb should appear in the spread_arb view.
    await _seed_prediction(session, market=market, model_id="spread_arb", edge=0.10)
    await _seed_prediction(session, market=market, model_id="elo_sports", edge=-0.05)

    ctx = await build_context(session, "spread_arb")
    assert ctx is not None
    assert len(ctx.recent_predictions) == 1
    assert ctx.recent_predictions[0]["edge"] == pytest.approx(0.10, rel=1e-6)
