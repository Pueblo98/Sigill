"""Tests for the model_brier widget."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from uuid import uuid4

import pytest

from sigil.dashboard.widgets.model_brier import (
    ModelBrierConfig,
    ModelBrierWidget,
)
from sigil.models import Market, Prediction


def _make_widget() -> ModelBrierWidget:
    return ModelBrierWidget(ModelBrierConfig(type="model_brier", cache="1h"))


def _add_settled_market(session, *, settlement: float = 1.0) -> Market:
    m = Market(
        platform="kalshi",
        external_id=f"S-{uuid4().hex[:6]}",
        title="settled market",
        taxonomy_l1="weather",
        status="settled",
        settlement_value=settlement,
    )
    session.add(m)
    return m


@pytest.mark.asyncio
async def test_empty_state(session):
    w = _make_widget()
    data = await w.fetch(session)
    assert data == []
    assert "No settled predictions yet." in w.render(data)


@pytest.mark.asyncio
async def test_only_unsettled_predictions_yield_empty(session):
    open_market = Market(
        platform="kalshi",
        external_id="O-1",
        title="open",
        taxonomy_l1="x",
        status="open",
    )
    session.add(open_market)
    await session.commit()
    await session.refresh(open_market)
    session.add(
        Prediction(
            market_id=open_market.id,
            model_id="m1",
            model_version="1",
            predicted_prob=0.6,
        )
    )
    await session.commit()

    w = _make_widget()
    data = await w.fetch(session)
    assert data == []


@pytest.mark.asyncio
async def test_brier_30d_and_90d_split(session):
    now = datetime.now(timezone.utc)

    market_yes = _add_settled_market(session, settlement=1.0)
    market_no = _add_settled_market(session, settlement=0.0)
    await session.commit()
    await session.refresh(market_yes)
    await session.refresh(market_no)

    # Two recent (within 30d) predictions for model A — both correct.
    session.add_all(
        [
            Prediction(
                market_id=market_yes.id,
                model_id="model_a",
                model_version="1",
                predicted_prob=0.9,
                created_at=now - timedelta(days=2),
            ),
            Prediction(
                market_id=market_no.id,
                model_id="model_a",
                model_version="1",
                predicted_prob=0.1,
                created_at=now - timedelta(days=10),
            ),
            # An older (60d) prediction for model A — should appear in 90d only.
            Prediction(
                market_id=market_yes.id,
                model_id="model_a",
                model_version="1",
                predicted_prob=0.5,
                created_at=now - timedelta(days=60),
            ),
            # A different model with one recent prediction.
            Prediction(
                market_id=market_yes.id,
                model_id="model_b",
                model_version="1",
                predicted_prob=0.5,
                created_at=now - timedelta(days=1),
            ),
        ]
    )
    await session.commit()

    w = _make_widget()
    data = await w.fetch(session)
    assert len(data) == 2

    a = next(r for r in data if r.model_id == "model_a")
    b = next(r for r in data if r.model_id == "model_b")

    assert a.n_30d == 2
    # ((0.9-1)^2 + (0.1-0)^2) / 2 = (0.01 + 0.01)/2 = 0.01
    assert a.brier_30d == pytest.approx(0.01)
    assert a.n_90d == 3
    # add (0.5-1)^2 = 0.25; (0.01+0.01+0.25)/3 = 0.09
    assert a.brier_90d == pytest.approx(0.09)

    assert b.n_30d == 1
    # (0.5-1)^2 / 1 = 0.25
    assert b.brier_30d == pytest.approx(0.25)


@pytest.mark.asyncio
async def test_renders_table_with_data_widget_type(session):
    market = _add_settled_market(session, settlement=1.0)
    await session.commit()
    await session.refresh(market)
    session.add(
        Prediction(
            market_id=market.id,
            model_id="m1",
            model_version="1",
            predicted_prob=0.7,
            created_at=datetime.now(timezone.utc),
        )
    )
    await session.commit()

    w = _make_widget()
    data = await w.fetch(session)
    out = w.render(data)
    assert 'data-widget-type="model_brier"' in out
    assert "Brier 30d" in out
    assert "m1" in out
