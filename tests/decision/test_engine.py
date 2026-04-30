"""Decision-engine tests: edge math, platform gating, and orchestration.

Marked `critical` — these are on the 12 critical paths in REVIEW-DECISIONS.md 3B.
"""

from __future__ import annotations

import math
from types import SimpleNamespace
from uuid import uuid4

import pytest

from sigil.config import config
from sigil.decision.drawdown import DrawdownState
from sigil.decision.engine import (
    DecisionEngine,
    DecisionResult,
    compute_edge,
    should_trade,
)


pytestmark = pytest.mark.critical


# ─── compute_edge ─────────────────────────────────────────────────────────────


def test_compute_edge_happy_path():
    edge = compute_edge(p_model=0.70, p_market=0.50, confidence=1.0)
    assert edge == pytest.approx(0.20)


def test_compute_edge_applies_confidence_weighting():
    edge = compute_edge(p_model=0.70, p_market=0.50, confidence=0.5)
    assert edge == pytest.approx(0.10)


def test_compute_edge_negative_when_model_below_market():
    edge = compute_edge(p_model=0.30, p_market=0.50, confidence=0.8)
    assert edge == pytest.approx(-0.16)


def test_compute_edge_zero_when_market_at_lower_boundary():
    assert compute_edge(0.7, 0.0, 1.0) == 0.0


def test_compute_edge_zero_when_market_at_upper_boundary():
    assert compute_edge(0.7, 1.0, 1.0) == 0.0


def test_compute_edge_rejects_nan_p_model():
    with pytest.raises(ValueError):
        compute_edge(float("nan"), 0.5, 1.0)


def test_compute_edge_rejects_nan_p_market():
    with pytest.raises(ValueError):
        compute_edge(0.5, float("nan"), 1.0)


def test_compute_edge_rejects_nan_confidence():
    with pytest.raises(ValueError):
        compute_edge(0.5, 0.5, float("nan"))


def test_compute_edge_rejects_negative_confidence():
    with pytest.raises(ValueError):
        compute_edge(0.5, 0.4, -0.1)


def test_compute_edge_rejects_confidence_above_one():
    with pytest.raises(ValueError):
        compute_edge(0.5, 0.4, 1.1)


def test_compute_edge_rejects_p_model_out_of_range():
    with pytest.raises(ValueError):
        compute_edge(1.5, 0.4, 1.0)


def test_compute_edge_rejects_p_market_out_of_range():
    with pytest.raises(ValueError):
        compute_edge(0.5, -0.1, 1.0)


# ─── should_trade ─────────────────────────────────────────────────────────────


def test_should_trade_kalshi_above_threshold():
    edge = config.MIN_EDGE_KALSHI + 0.01
    assert should_trade(edge, "kalshi") is True


def test_should_trade_kalshi_at_threshold_is_false():
    # Strict > comparison, not >=
    assert should_trade(config.MIN_EDGE_KALSHI, "kalshi") is False


def test_should_trade_kalshi_below_threshold():
    edge = config.MIN_EDGE_KALSHI - 0.01
    assert should_trade(edge, "kalshi") is False


def test_should_trade_polymarket_always_false_per_1c(caplog):
    huge_edge = 0.99
    with caplog.at_level("WARNING"):
        result = should_trade(huge_edge, "polymarket")
    assert result is False
    assert any("display-only" in r.message.lower() or "polymarket" in r.message.lower()
               for r in caplog.records)


def test_should_trade_polymarket_case_insensitive():
    assert should_trade(0.99, "Polymarket") is False
    assert should_trade(0.99, "POLYMARKET") is False


def test_should_trade_unknown_platform_false():
    assert should_trade(0.99, "augur") is False


def test_should_trade_rejects_nan():
    with pytest.raises(ValueError):
        should_trade(float("nan"), "kalshi")


# ─── DecisionEngine orchestration ─────────────────────────────────────────────


def _prediction(predicted_prob: float, confidence: float = 1.0):
    return SimpleNamespace(
        id=uuid4(),
        predicted_prob=predicted_prob,
        confidence=confidence,
    )


@pytest.mark.asyncio
async def test_engine_submits_when_all_gates_pass():
    calls: list[dict] = []

    async def fake_oms_submit(**kwargs):
        calls.append(kwargs)
        return {"order_id": uuid4(), "status": "created"}

    async def stub_drawdown(session, mode="paper"):
        return DrawdownState.INACTIVE

    engine = DecisionEngine(
        oms_submit=fake_oms_submit,
        drawdown_state_fn=stub_drawdown,
    )

    result = await engine.evaluate(
        session=None,
        prediction=_prediction(0.80, confidence=1.0),
        market_price=0.50,
        platform="kalshi",
        market_id=uuid4(),
    )

    assert result.accepted is True
    assert result.reason == "submitted"
    assert math.isclose(result.edge, 0.30, rel_tol=1e-9)
    assert result.size_multiplier == 1.0
    assert len(calls) == 1
    assert calls[0]["platform"] == "kalshi"
    assert calls[0]["edge_at_entry"] == pytest.approx(0.30)


@pytest.mark.asyncio
async def test_engine_rejects_below_threshold_without_calling_oms():
    calls: list[dict] = []

    async def fake_oms_submit(**kwargs):
        calls.append(kwargs)
        return None

    async def stub_drawdown(session, mode="paper"):
        return DrawdownState.INACTIVE

    engine = DecisionEngine(
        oms_submit=fake_oms_submit,
        drawdown_state_fn=stub_drawdown,
    )

    result = await engine.evaluate(
        session=None,
        prediction=_prediction(0.55, confidence=1.0),
        market_price=0.50,
        platform="kalshi",
        market_id=uuid4(),
    )

    assert result.accepted is False
    assert result.reason == "edge_below_threshold"
    assert calls == []


@pytest.mark.asyncio
async def test_engine_rejects_polymarket_logs_display_only(caplog):
    calls: list[dict] = []

    async def fake_oms_submit(**kwargs):
        calls.append(kwargs)
        return None

    async def stub_drawdown(session, mode="paper"):
        return DrawdownState.INACTIVE

    engine = DecisionEngine(
        oms_submit=fake_oms_submit,
        drawdown_state_fn=stub_drawdown,
    )

    with caplog.at_level("INFO"):
        result = await engine.evaluate(
            session=None,
            prediction=_prediction(0.95, confidence=1.0),
            market_price=0.20,
            platform="polymarket",
            market_id=uuid4(),
        )

    assert result.accepted is False
    assert result.reason == "polymarket_display_only"
    assert calls == []
    assert any("display-only" in r.message.lower() or "polymarket" in r.message.lower()
               for r in caplog.records)


@pytest.mark.asyncio
async def test_engine_halts_when_drawdown_in_halt_state():
    calls: list[dict] = []

    async def fake_oms_submit(**kwargs):
        calls.append(kwargs)
        return None

    async def stub_drawdown(session, mode="paper"):
        return DrawdownState.HALT

    engine = DecisionEngine(
        oms_submit=fake_oms_submit,
        drawdown_state_fn=stub_drawdown,
    )

    result = await engine.evaluate(
        session=None,
        prediction=_prediction(0.80, confidence=1.0),
        market_price=0.50,
        platform="kalshi",
        market_id=uuid4(),
    )

    assert result.accepted is False
    assert result.reason == "drawdown_halt"
    assert result.size_multiplier == 0.0
    assert calls == []


@pytest.mark.asyncio
async def test_engine_passes_warning_multiplier_to_oms():
    calls: list[dict] = []

    async def fake_oms_submit(**kwargs):
        calls.append(kwargs)
        return {"order_id": uuid4()}

    async def stub_drawdown(session, mode="paper"):
        return DrawdownState.WARNING

    engine = DecisionEngine(
        oms_submit=fake_oms_submit,
        drawdown_state_fn=stub_drawdown,
    )

    result = await engine.evaluate(
        session=None,
        prediction=_prediction(0.80, confidence=1.0),
        market_price=0.50,
        platform="kalshi",
        market_id=uuid4(),
    )

    assert result.accepted is True
    assert result.size_multiplier == 0.5
    assert calls[0]["size_multiplier"] == 0.5


@pytest.mark.asyncio
async def test_engine_handles_synchronous_oms_callable():
    calls: list[dict] = []

    def sync_oms_submit(**kwargs):
        calls.append(kwargs)
        return "synchronous-return"

    async def stub_drawdown(session, mode="paper"):
        return DrawdownState.INACTIVE

    engine = DecisionEngine(
        oms_submit=sync_oms_submit,
        drawdown_state_fn=stub_drawdown,
    )

    result = await engine.evaluate(
        session=None,
        prediction=_prediction(0.80, confidence=1.0),
        market_price=0.50,
        platform="kalshi",
        market_id=uuid4(),
    )

    assert result.accepted is True
    assert result.oms_response == "synchronous-return"
    assert len(calls) == 1


def test_decision_result_dataclass_fields():
    """Sanity check on the public DecisionResult shape."""
    r = DecisionResult(
        accepted=True,
        reason="submitted",
        edge=0.1,
        weighted_edge=0.1,
        drawdown_state=DrawdownState.INACTIVE,
        size_multiplier=1.0,
    )
    assert r.accepted is True
    assert r.oms_response is None
