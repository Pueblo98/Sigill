"""Tests for the model_calibration widget."""

from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

import pytest

from sigil.dashboard.widgets.model_calibration import (
    ModelCalibrationConfig,
    ModelCalibrationWidget,
)
from sigil.models import Market, Prediction


def _make_widget(top_n: int = 1, n_bins: int = 10) -> ModelCalibrationWidget:
    return ModelCalibrationWidget(
        ModelCalibrationConfig(
            type="model_calibration", cache="1h", top_n=top_n, n_bins=n_bins
        )
    )


def _settled_market(session, settlement: float) -> Market:
    m = Market(
        platform="kalshi",
        external_id=f"C-{uuid4().hex[:6]}",
        title="settled",
        taxonomy_l1="x",
        status="settled",
        settlement_value=settlement,
    )
    session.add(m)
    return m


@pytest.mark.asyncio
async def test_empty_state(session):
    w = _make_widget()
    assert await w.fetch(session) == []
    out = w.render(await w.fetch(session))
    assert "30+ settled predictions" in out


@pytest.mark.asyncio
async def test_below_threshold_returns_empty(session):
    market = _settled_market(session, 1.0)
    await session.commit()
    await session.refresh(market)
    # Only 5 predictions — below the 30 minimum.
    session.add_all(
        [
            Prediction(
                market_id=market.id,
                model_id="m1",
                model_version="1",
                predicted_prob=0.5 + i * 0.01,
                created_at=datetime.now(timezone.utc),
            )
            for i in range(5)
        ]
    )
    await session.commit()

    w = _make_widget()
    assert await w.fetch(session) == []


@pytest.mark.asyncio
async def test_calibration_renders_for_eligible_model(session):
    yes = _settled_market(session, 1.0)
    no = _settled_market(session, 0.0)
    await session.commit()
    await session.refresh(yes)
    await session.refresh(no)

    preds = []
    # 30 perfectly-calibrated predictions: probs evenly spaced, half on each
    # outcome; this is enough to clear the threshold.
    for i in range(30):
        preds.append(
            Prediction(
                market_id=yes.id if i % 2 == 0 else no.id,
                model_id="modelA",
                model_version="1",
                predicted_prob=(i + 1) / 32.0,
                created_at=datetime.now(timezone.utc),
            )
        )
    session.add_all(preds)
    await session.commit()

    w = _make_widget(top_n=1, n_bins=5)
    data = await w.fetch(session)
    assert len(data) == 1
    view = data[0]
    assert view.model_id == "modelA"
    assert view.n_predictions == 30
    assert view.bins  # at least one populated bin
    assert "<svg" in view.svg

    out = w.render(data)
    assert 'data-widget-type="model_calibration"' in out
    assert "modelA" in out
    assert "<svg" in out


@pytest.mark.asyncio
async def test_top_n_limits_models(session):
    yes = _settled_market(session, 1.0)
    no = _settled_market(session, 0.0)
    await session.commit()
    await session.refresh(yes)
    await session.refresh(no)

    # modelA gets 40 predictions, modelB gets 35 — both eligible. top_n=1
    # should pick modelA.
    rows = []
    for i in range(40):
        rows.append(
            Prediction(
                market_id=yes.id if i % 2 == 0 else no.id,
                model_id="modelA",
                model_version="1",
                predicted_prob=0.5,
                created_at=datetime.now(timezone.utc),
            )
        )
    for i in range(35):
        rows.append(
            Prediction(
                market_id=yes.id if i % 2 == 0 else no.id,
                model_id="modelB",
                model_version="1",
                predicted_prob=0.5,
                created_at=datetime.now(timezone.utc),
            )
        )
    session.add_all(rows)
    await session.commit()

    w = _make_widget(top_n=1)
    data = await w.fetch(session)
    assert len(data) == 1
    assert data[0].model_id == "modelA"
