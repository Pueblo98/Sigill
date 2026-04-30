"""W2.2(a) — DecisionEngine ↔ OMS wiring.

Confirms a positive-edge `Prediction` flows through `DecisionEngine.evaluate()`
and lands as a real `Order` row written by Lane A's `OMS`.
"""
from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

import pytest
from sqlalchemy import select

from sigil.decision.drawdown import DrawdownState
from sigil.decision.engine import DecisionEngine
from sigil.decision.wiring import make_oms_submit
from sigil.execution.oms import OMS, OrderState
from sigil.models import MarketPrice, Order, Prediction


pytestmark = pytest.mark.critical


@pytest.mark.asyncio
async def test_engine_to_oms_writes_order_row(session, sample_market):
    market_price = MarketPrice(
        time=datetime.now(timezone.utc),
        market_id=sample_market.id,
        bid=0.49,
        ask=0.51,
        last_price=0.50,
        source="kalshi",
    )
    session.add(market_price)
    prediction = Prediction(
        id=uuid4(),
        market_id=sample_market.id,
        model_id="test-model",
        model_version="v1",
        predicted_prob=0.75,
        confidence=1.0,
        market_price_at_prediction=0.50,
        edge=0.25,
    )
    session.add(prediction)
    await session.commit()

    oms = OMS(session=session)
    submit = make_oms_submit(oms)

    async def stub_drawdown(_session, mode="paper"):
        return DrawdownState.INACTIVE

    engine = DecisionEngine(oms_submit=submit, drawdown_state_fn=stub_drawdown, mode="paper")

    result = await engine.evaluate(
        session=session,
        prediction=prediction,
        market_price=0.50,
        platform="kalshi",
        market_id=sample_market.id,
    )
    await session.commit()

    assert result.accepted is True
    assert result.reason == "submitted"

    rows = (await session.execute(select(Order))).scalars().all()
    assert len(rows) == 1
    order = rows[0]
    assert order.market_id == sample_market.id
    assert order.platform == "kalshi"
    assert order.mode == "paper"
    assert order.side == "buy"
    assert order.outcome == "yes"
    assert order.quantity > 0
    assert order.client_order_id.startswith("sigil_")
    # Paper mode short-circuits to FILLED in OMS._simulate_paper_fill.
    assert order.status == OrderState.FILLED
    assert order.filled_quantity == order.quantity
    assert order.prediction_id == prediction.id
    assert order.edge_at_entry == pytest.approx(0.25)


@pytest.mark.asyncio
async def test_engine_to_oms_skips_when_no_market_price(session, sample_market):
    prediction = Prediction(
        id=uuid4(),
        market_id=sample_market.id,
        model_id="test-model",
        model_version="v1",
        predicted_prob=0.75,
        confidence=1.0,
    )
    session.add(prediction)
    await session.commit()

    oms = OMS(session=session)
    submit = make_oms_submit(oms)

    async def stub_drawdown(_session, mode="paper"):
        return DrawdownState.INACTIVE

    engine = DecisionEngine(oms_submit=submit, drawdown_state_fn=stub_drawdown, mode="paper")

    result = await engine.evaluate(
        session=session,
        prediction=prediction,
        market_price=0.50,
        platform="kalshi",
        market_id=sample_market.id,
    )
    await session.commit()

    assert result.accepted is True  # engine accepted; adapter skipped due to no price
    assert result.oms_response is None
    rows = (await session.execute(select(Order))).scalars().all()
    assert rows == []


@pytest.mark.asyncio
async def test_engine_to_oms_drawdown_halt_skips_oms(session, sample_market):
    prediction = Prediction(
        id=uuid4(),
        market_id=sample_market.id,
        model_id="test-model",
        model_version="v1",
        predicted_prob=0.75,
        confidence=1.0,
        market_price_at_prediction=0.50,
    )
    session.add(prediction)
    await session.commit()

    oms = OMS(session=session)
    submit = make_oms_submit(oms)

    async def halted(_session, mode="paper"):
        return DrawdownState.HALT

    engine = DecisionEngine(oms_submit=submit, drawdown_state_fn=halted, mode="paper")

    result = await engine.evaluate(
        session=session,
        prediction=prediction,
        market_price=0.50,
        platform="kalshi",
        market_id=sample_market.id,
    )
    await session.commit()

    assert result.accepted is False
    assert result.reason == "drawdown_halt"
    rows = (await session.execute(select(Order))).scalars().all()
    assert rows == []
