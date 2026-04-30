"""Kelly sizing — hand-computed examples + every documented edge case."""
from __future__ import annotations

import math

import pytest

from sigil.config import config
from sigil.execution.sizing import kelly_size


# Hand-computed: p_model=0.6, p_market=0.4, bankroll=1000
#   odds = 1/0.4 - 1 = 1.5
#   edge = 0.2
#   kelly_pct_full = (0.2*2.5 - 0.4)/1.5 = (0.5 - 0.4)/1.5 = 0.0666...
#   With KELLY_FRACTION=0.25 -> 0.01666...
#   bankroll * 0.01666... = 16.666...
@pytest.mark.critical
def test_kelly_hand_computed_example():
    result = kelly_size(p_model=0.6, p_market=0.4, bankroll=1000.0)
    assert math.isclose(result.kelly_fraction_used, 0.0666666 * config.KELLY_FRACTION, rel_tol=1e-3)
    assert math.isclose(result.bet_amount, 1000 * 0.0666666 * config.KELLY_FRACTION, rel_tol=1e-3)
    assert result.capped is False


@pytest.mark.critical
def test_kelly_full_fraction_matches_textbook():
    # Full Kelly (fraction=1.0). Override max_position_pct so the cap doesn't
    # short-circuit the textbook value of 6.67%.
    result = kelly_size(
        p_model=0.6,
        p_market=0.4,
        bankroll=1000.0,
        fraction=1.0,
        max_position_pct=100.0,
    )
    assert math.isclose(result.kelly_fraction_used, 0.0666666, rel_tol=1e-3)


@pytest.mark.critical
@pytest.mark.parametrize("p_market", [0.0, 1.0, -0.1, 1.5])
def test_p_market_out_of_open_unit_interval_returns_zero(p_market):
    result = kelly_size(p_model=0.6, p_market=p_market, bankroll=1000.0)
    assert result.bet_amount == 0.0


@pytest.mark.critical
def test_p_model_le_p_market_returns_zero():
    assert kelly_size(0.4, 0.4, 1000.0).bet_amount == 0.0
    assert kelly_size(0.3, 0.4, 1000.0).bet_amount == 0.0


@pytest.mark.critical
def test_negative_confidence_raises():
    with pytest.raises(ValueError):
        kelly_size(0.6, 0.4, 1000.0, confidence=-0.1)


@pytest.mark.critical
def test_nan_inputs_raise():
    with pytest.raises(ValueError):
        kelly_size(float("nan"), 0.4, 1000.0)
    with pytest.raises(ValueError):
        kelly_size(0.6, float("nan"), 1000.0)
    with pytest.raises(ValueError):
        kelly_size(0.6, 0.4, float("nan"))
    with pytest.raises(ValueError):
        kelly_size(0.6, 0.4, 1000.0, fraction=float("nan"))


@pytest.mark.critical
def test_capped_at_max_position_pct():
    # Force a strong edge so kelly_pct_full would exceed cap.
    result = kelly_size(p_model=0.95, p_market=0.05, bankroll=10_000.0, fraction=1.0)
    cap_pct = config.MAX_POSITION_PCT / 100.0
    assert result.capped is True
    assert math.isclose(result.kelly_fraction_used, cap_pct)
    assert math.isclose(result.bet_amount, 10_000.0 * cap_pct)


@pytest.mark.critical
def test_zero_bankroll_returns_zero():
    assert kelly_size(0.6, 0.4, 0.0).bet_amount == 0.0
    assert kelly_size(0.6, 0.4, -100.0).bet_amount == 0.0


def test_p_model_above_one_raises():
    with pytest.raises(ValueError):
        kelly_size(p_model=1.5, p_market=0.4, bankroll=1000.0)


def test_confidence_scales_kelly():
    base = kelly_size(0.6, 0.4, 1000.0)
    half = kelly_size(0.6, 0.4, 1000.0, confidence=0.5)
    assert math.isclose(half.bet_amount, base.bet_amount * 0.5, rel_tol=1e-9)
