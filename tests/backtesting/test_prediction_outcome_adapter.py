"""W2.2(g) — adapter from ORM Prediction + Market to metrics.all_metrics input."""
from __future__ import annotations

from types import SimpleNamespace
from uuid import uuid4

import pytest

from sigil.backtesting.metrics import (
    PredictionOutcome,
    all_metrics,
    brier_score,
    prediction_outcomes_from_orm,
)


def test_adapter_settlement_value_one_maps_to_outcome_one():
    market_id = uuid4()
    pred = SimpleNamespace(predicted_prob=0.8, market_id=market_id)
    market = SimpleNamespace(settlement_value=1.0)
    out = prediction_outcomes_from_orm([pred], {market_id: market})
    assert len(out) == 1
    assert out[0].outcome == 1
    assert out[0].predicted_prob == pytest.approx(0.8)


def test_adapter_settlement_value_zero_maps_to_outcome_zero():
    market_id = uuid4()
    pred = SimpleNamespace(predicted_prob=0.1, market_id=market_id)
    market = SimpleNamespace(settlement_value=0.0)
    out = prediction_outcomes_from_orm([pred], {market_id: market})
    assert out[0].outcome == 0


def test_adapter_drops_unsettled_predictions():
    market_id = uuid4()
    pred = SimpleNamespace(predicted_prob=0.8, market_id=market_id)
    market = SimpleNamespace(settlement_value=None)
    out = prediction_outcomes_from_orm([pred], {market_id: market})
    assert out == []


def test_adapter_drops_predictions_with_missing_market():
    pred = SimpleNamespace(predicted_prob=0.8, market_id=uuid4())
    out = prediction_outcomes_from_orm([pred], {})
    assert out == []


def test_adapter_uses_yes_threshold_for_fractional_settlement():
    market_id = uuid4()
    pred_high = SimpleNamespace(predicted_prob=0.5, market_id=market_id)
    market_at_threshold = SimpleNamespace(settlement_value=0.5)
    out = prediction_outcomes_from_orm([pred_high], {market_id: market_at_threshold})
    assert out[0].outcome == 1  # >= 0.5

    market_below = SimpleNamespace(settlement_value=0.49)
    out = prediction_outcomes_from_orm([pred_high], {market_id: market_below})
    assert out[0].outcome == 0


def test_adapter_falls_back_to_prediction_dot_market_when_lookup_empty():
    market = SimpleNamespace(settlement_value=1.0)
    pred = SimpleNamespace(predicted_prob=0.7, market_id=uuid4(), market=market)
    out = prediction_outcomes_from_orm([pred], {})
    assert len(out) == 1
    assert out[0].outcome == 1


def test_adapter_output_feeds_all_metrics():
    """End-to-end: the adapter shape must satisfy `all_metrics(predictions=...)`."""
    outcomes = [
        PredictionOutcome(predicted_prob=0.9, outcome=1),
        PredictionOutcome(predicted_prob=0.2, outcome=0),
        PredictionOutcome(predicted_prob=0.5, outcome=1),
    ]
    fake_result = SimpleNamespace(
        equity_curve=[],
        trades=[],
        final_equity=0.0,
        config=SimpleNamespace(initial_capital=1000.0),
    )
    metrics = all_metrics(fake_result, predictions=outcomes)
    expected_brier = brier_score([0.9, 0.2, 0.5], [1, 0, 1])
    assert metrics["brier"] == pytest.approx(expected_brier)
    assert "log_loss" in metrics
    assert "calibration_error" in metrics
