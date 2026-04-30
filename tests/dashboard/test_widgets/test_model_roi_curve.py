"""Tests for the model_roi_curve widget."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from uuid import uuid4

import pytest

from sigil.dashboard.widgets.model_roi_curve import (
    ModelRoiCurveConfig,
    ModelRoiCurveWidget,
)
from sigil.models import Market, Order, Position, Prediction


def _make_widget() -> ModelRoiCurveWidget:
    return ModelRoiCurveWidget(
        ModelRoiCurveConfig(type="model_roi_curve", cache="1h")
    )


@pytest.mark.asyncio
async def test_empty_state(session):
    w = _make_widget()
    data = await w.fetch(session)
    assert data == []
    assert "No settled positions yet." in w.render(data)


@pytest.mark.asyncio
async def test_curve_built_from_settled_positions(session):
    market_a = Market(
        platform="kalshi",
        external_id=f"R-{uuid4().hex[:6]}",
        title="market a",
        taxonomy_l1="x",
        status="settled",
        settlement_value=1.0,
    )
    market_b = Market(
        platform="kalshi",
        external_id=f"R-{uuid4().hex[:6]}",
        title="market b",
        taxonomy_l1="x",
        status="settled",
        settlement_value=0.0,
    )
    session.add_all([market_a, market_b])
    await session.commit()
    await session.refresh(market_a)
    await session.refresh(market_b)

    pred_a = Prediction(
        market_id=market_a.id,
        model_id="alpha",
        model_version="1",
        predicted_prob=0.7,
    )
    pred_b = Prediction(
        market_id=market_b.id,
        model_id="alpha",
        model_version="1",
        predicted_prob=0.3,
    )
    session.add_all([pred_a, pred_b])
    await session.commit()
    await session.refresh(pred_a)
    await session.refresh(pred_b)

    session.add_all(
        [
            Order(
                client_order_id=f"sigil_{uuid4().hex}",
                platform="kalshi",
                market_id=market_a.id,
                prediction_id=pred_a.id,
                mode="paper",
                side="buy",
                outcome="yes",
                order_type="limit",
                price=0.5,
                quantity=10,
                status="filled",
            ),
            Order(
                client_order_id=f"sigil_{uuid4().hex}",
                platform="kalshi",
                market_id=market_b.id,
                prediction_id=pred_b.id,
                mode="paper",
                side="buy",
                outcome="yes",
                order_type="limit",
                price=0.5,
                quantity=10,
                status="filled",
            ),
        ]
    )

    base = datetime.now(timezone.utc) - timedelta(days=3)
    session.add_all(
        [
            Position(
                platform="kalshi",
                market_id=market_a.id,
                mode="paper",
                outcome="yes",
                quantity=10,
                avg_entry_price=0.5,
                realized_pnl=20.0,
                status="closed",
                opened_at=base,
                closed_at=base + timedelta(days=1),
            ),
            Position(
                platform="kalshi",
                market_id=market_b.id,
                mode="paper",
                outcome="yes",
                quantity=10,
                avg_entry_price=0.5,
                realized_pnl=-5.0,
                status="settled",
                opened_at=base,
                closed_at=base + timedelta(days=2),
            ),
        ]
    )
    await session.commit()

    w = _make_widget()
    data = await w.fetch(session)
    assert len(data) == 1
    curve = data[0]
    assert curve.model_id == "alpha"
    assert curve.n_trades == 2
    # cumulative: 20, then 20 - 5 = 15
    assert curve.points[0][1] == pytest.approx(20.0)
    assert curve.points[-1][1] == pytest.approx(15.0)
    assert curve.final_equity == pytest.approx(15.0)
    assert "<svg" in curve.svg

    out = w.render(data)
    assert 'data-widget-type="model_roi_curve"' in out
    assert "alpha" in out


@pytest.mark.asyncio
async def test_position_without_prediction_is_skipped(session):
    market = Market(
        platform="kalshi",
        external_id="ORPHAN",
        title="orphan",
        taxonomy_l1="x",
        status="settled",
        settlement_value=1.0,
    )
    session.add(market)
    await session.commit()
    await session.refresh(market)
    session.add(
        Position(
            platform="kalshi",
            market_id=market.id,
            mode="paper",
            outcome="yes",
            quantity=1,
            avg_entry_price=0.5,
            realized_pnl=1.0,
            status="closed",
            opened_at=datetime.now(timezone.utc),
            closed_at=datetime.now(timezone.utc),
        )
    )
    await session.commit()

    w = _make_widget()
    data = await w.fetch(session)
    assert data == []
