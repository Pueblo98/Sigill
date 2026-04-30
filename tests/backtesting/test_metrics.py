"""Hand-computed metric tests. Critical-path per REVIEW-DECISIONS.md 3B."""

from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Optional

import pytest

from sigil.backtesting.engine import BacktestConfig, BacktestResult, Trade
from sigil.backtesting.metrics import (
    all_metrics,
    avg_edge_captured,
    brier_score,
    calibration_curve,
    calibration_error,
    log_loss,
    max_drawdown,
    roi,
    sharpe_equivalent,
    win_rate,
)


@pytest.mark.critical
def test_brier_three_coinflips():
    """predictions=[0.5,0.5,0.5], outcomes=[1,0,1] -> 0.25 exactly."""
    assert brier_score([0.5, 0.5, 0.5], [1, 0, 1]) == pytest.approx(0.25)


@pytest.mark.critical
def test_brier_perfect_forecaster():
    """predictions=[1.0,0.0], outcomes=[1,0] -> 0.0 exactly."""
    assert brier_score([1.0, 0.0], [1, 0]) == 0.0


@pytest.mark.critical
def test_brier_perfectly_wrong_forecaster():
    """predictions=[1.0,0.0], outcomes=[0,1] -> 1.0 exactly."""
    assert brier_score([1.0, 0.0], [0, 1]) == 1.0


@pytest.mark.critical
def test_brier_mixed_handcomputed():
    """predictions=[0.8,0.3], outcomes=[1,0] -> ((0.8-1)^2 + (0.3-0)^2)/2 = (0.04+0.09)/2 = 0.065."""
    assert brier_score([0.8, 0.3], [1, 0]) == pytest.approx(0.065)


@pytest.mark.critical
def test_brier_validates_inputs():
    with pytest.raises(ValueError):
        brier_score([0.5], [1, 0])
    with pytest.raises(ValueError):
        brier_score([1.5], [1])
    with pytest.raises(ValueError):
        brier_score([0.5], [2])
    with pytest.raises(ValueError):
        brier_score([], [])


@pytest.mark.critical
def test_log_loss_coin_flip():
    """predictions=[0.5,0.5], outcomes=[1,0] -> ln(2) ~ 0.6931."""
    assert log_loss([0.5, 0.5], [1, 0]) == pytest.approx(math.log(2.0), rel=1e-12)


@pytest.mark.critical
def test_log_loss_clips_zero_one():
    """log loss should not produce inf/nan when given 0 or 1 with a wrong outcome."""
    val = log_loss([0.0, 1.0], [1, 0])
    assert math.isfinite(val)
    assert val > 0


@pytest.mark.critical
def test_log_loss_perfect():
    val = log_loss([1.0, 0.0], [1, 0])
    assert val == pytest.approx(0.0, abs=1e-12)


@pytest.mark.critical
def test_calibration_error_well_calibrated():
    """Construct a perfectly calibrated dataset: in each bin, observed
    frequency exactly matches predicted probability -> error = 0."""
    preds: list[float] = []
    outs: list[int] = []
    # Bin centers: 0.05, 0.15, ... 0.95. Use 100 samples per bin; first
    # int(round(center*100)) are 1s, rest 0s, so observed freq matches center.
    for center in [0.05, 0.15, 0.25, 0.35, 0.45, 0.55, 0.65, 0.75, 0.85, 0.95]:
        n = 100
        n_pos = int(round(center * n))
        preds.extend([center] * n)
        outs.extend([1] * n_pos + [0] * (n - n_pos))
    err = calibration_error(preds, outs, n_bins=10)
    assert err == pytest.approx(0.0, abs=1e-9)


@pytest.mark.critical
def test_calibration_error_bounded():
    """Predict 0.9 always while outcome is always 0 -> error ~ 0.9."""
    preds = [0.9] * 50
    outs = [0] * 50
    err = calibration_error(preds, outs, n_bins=10)
    assert err == pytest.approx(0.9)


@pytest.mark.critical
def test_calibration_curve_returns_per_bin():
    preds = [0.1, 0.1, 0.9, 0.9]
    outs = [0, 0, 1, 1]
    mean_pred, observed = calibration_curve(preds, outs, n_bins=10)
    assert len(mean_pred) == 2
    assert len(observed) == 2
    assert mean_pred[0] == pytest.approx(0.1)
    assert observed[0] == pytest.approx(0.0)
    assert mean_pred[1] == pytest.approx(0.9)
    assert observed[1] == pytest.approx(1.0)


@pytest.mark.critical
def test_max_drawdown_peak_then_drop():
    """Equity goes 100 -> 150 -> 75 -> drawdown is (150-75)/150 = 0.5."""
    base = datetime(2026, 1, 1)
    curve = [
        (base, 100.0),
        (base + timedelta(days=1), 150.0),
        (base + timedelta(days=2), 75.0),
    ]
    assert max_drawdown(curve) == pytest.approx(0.5)


@pytest.mark.critical
def test_max_drawdown_monotonic_no_drawdown():
    base = datetime(2026, 1, 1)
    curve = [(base + timedelta(days=i), 100.0 + i) for i in range(5)]
    assert max_drawdown(curve) == 0.0


@pytest.mark.critical
def test_max_drawdown_empty_returns_zero():
    assert max_drawdown([]) == 0.0


def test_roi_doubled_capital():
    base = datetime(2026, 1, 1)
    curve = [(base, 5000.0), (base + timedelta(days=30), 10000.0)]
    assert roi(curve, 5000.0) == pytest.approx(1.0)


def test_roi_loss_handcomputed():
    base = datetime(2026, 1, 1)
    curve = [(base, 5000.0), (base + timedelta(days=30), 4000.0)]
    assert roi(curve, 5000.0) == pytest.approx(-0.2)


def test_sharpe_zero_variance_zero():
    base = datetime(2026, 1, 1)
    curve = [(base + timedelta(days=i), 100.0) for i in range(5)]
    assert sharpe_equivalent(curve) == 0.0


def test_sharpe_positive_for_uptrend():
    base = datetime(2026, 1, 1)
    curve = [(base + timedelta(days=i), 100.0 * (1.001 ** i) + (i % 2) * 0.1) for i in range(60)]
    s = sharpe_equivalent(curve)
    assert s > 0


def test_win_rate_handcomputed():
    base = datetime(2026, 1, 1)
    trades = [
        Trade(base, _uuid(), "buy", "yes", 10, 0.5, 0.7, realized_pnl=5.0),
        Trade(base, _uuid(), "buy", "yes", 10, 0.5, 0.7, realized_pnl=-3.0),
        Trade(base, _uuid(), "buy", "yes", 10, 0.5, 0.7, realized_pnl=2.0),
        Trade(base, _uuid(), "buy", "yes", 10, 0.5, 0.7, realized_pnl=None),
    ]
    assert win_rate(trades) == pytest.approx(2 / 3)


def test_win_rate_no_settled_trades():
    base = datetime(2026, 1, 1)
    trades = [Trade(base, _uuid(), "buy", "yes", 10, 0.5, 0.7, realized_pnl=None)]
    assert win_rate(trades) == 0.0


def test_avg_edge_captured_only_winners():
    base = datetime(2026, 1, 1)
    trades = [
        (
            Trade(base, _uuid(), "buy", "yes", 10, 0.5, 0.7,
                  realized_pnl=5.0, market_price_at_entry=0.4),
            _Pred(0.6),
        ),
        (
            Trade(base, _uuid(), "buy", "yes", 10, 0.5, 0.7,
                  realized_pnl=-1.0, market_price_at_entry=0.4),
            _Pred(0.6),
        ),
        (
            Trade(base, _uuid(), "buy", "yes", 10, 0.5, 0.7,
                  realized_pnl=3.0, market_price_at_entry=0.45),
            _Pred(0.55),
        ),
    ]
    edge = avg_edge_captured(trades)
    assert edge == pytest.approx(((0.6 - 0.4) + (0.55 - 0.45)) / 2)


def test_all_metrics_runs_without_predictions():
    base = datetime(2026, 1, 1)
    cfg = BacktestConfig(start_date=base, end_date=base + timedelta(days=30), initial_capital=5000.0)
    res = BacktestResult(
        config=cfg,
        trades=[Trade(base, _uuid(), "buy", "yes", 10, 0.5, 0.7, realized_pnl=1.0)],
        equity_curve=[(base, 5000.0), (base + timedelta(days=1), 5050.0)],
        final_equity=5050.0,
    )
    out = all_metrics(res)
    assert "roi" in out
    assert "max_drawdown" in out
    assert out["n_trades"] == 1


# helpers
def _uuid():
    from uuid import uuid4
    return uuid4()


@dataclass
class _Pred:
    predicted_prob: float
