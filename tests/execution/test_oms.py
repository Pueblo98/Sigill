"""OMS state-machine + idempotency tests."""
from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

import pytest

from sigil.execution.oms import (
    FillReport,
    IllegalStateTransition,
    OMS,
    OrderState,
    assert_transition,
    new_client_order_id,
)
from sigil.models import MarketPrice, Order


# --- pure transition-table tests ----------------------------------------- #

@pytest.mark.critical
def test_every_documented_transition_is_legal():
    legal = [
        (OrderState.CREATED, OrderState.SUBMITTED),
        (OrderState.SUBMITTED, OrderState.PENDING_ON_EXCHANGE),
        (OrderState.PENDING_ON_EXCHANGE, OrderState.FILLED),
        (OrderState.PENDING_ON_EXCHANGE, OrderState.PARTIALLY_FILLED),
        (OrderState.PENDING_ON_EXCHANGE, OrderState.REJECTED),
        (OrderState.PENDING_ON_EXCHANGE, OrderState.CANCELLED),
        (OrderState.PENDING_ON_EXCHANGE, OrderState.FAILED),
        (OrderState.PARTIALLY_FILLED, OrderState.FILLED),
        (OrderState.PARTIALLY_FILLED, OrderState.CANCELLED),
        (OrderState.SUBMITTED, OrderState.FAILED),
        (OrderState.SUBMITTED, OrderState.REJECTED),
    ]
    for src, dst in legal:
        assert_transition(src, dst)


@pytest.mark.critical
def test_terminal_states_reject_further_transitions():
    for terminal in (OrderState.FILLED, OrderState.REJECTED, OrderState.CANCELLED, OrderState.FAILED):
        with pytest.raises(IllegalStateTransition):
            assert_transition(terminal, OrderState.SUBMITTED)


@pytest.mark.critical
def test_invalid_skip_transition_raises():
    with pytest.raises(IllegalStateTransition):
        assert_transition(OrderState.CREATED, OrderState.FILLED)
    with pytest.raises(IllegalStateTransition):
        assert_transition(OrderState.CREATED, OrderState.PENDING_ON_EXCHANGE)


def test_client_order_id_format():
    coid = new_client_order_id()
    assert coid.startswith("sigil_")
    assert len(coid) > len("sigil_")


# --- paper short-circuit -------------------------------------------------- #

@pytest.mark.critical
async def test_paper_submit_simulates_fill_against_latest_price(session, sample_market):
    session.add(MarketPrice(
        time=datetime.now(timezone.utc),
        market_id=sample_market.id,
        source="exchange_ws",
        bid=0.41, ask=0.43, last_price=0.42,
    ))
    await session.commit()

    oms = OMS(session)
    order = await oms.create(
        platform="kalshi",
        market_id=sample_market.id,
        side="buy",
        outcome="yes",
        price=0.50,
        quantity=10,
        order_type="limit",
        mode="paper",
    )
    await session.commit()

    filled = await oms.submit(order, sample_market.external_id)
    await session.commit()

    assert filled.status == OrderState.FILLED
    assert filled.filled_quantity == 10
    assert float(filled.avg_fill_price) == 0.43  # buy fills at ask
    assert filled.external_order_id.startswith("paper_")


async def test_paper_submit_falls_back_to_order_price_when_no_market_price(session, sample_market):
    oms = OMS(session)
    order = await oms.create(
        platform="kalshi",
        market_id=sample_market.id,
        side="buy",
        outcome="yes",
        price=0.55,
        quantity=5,
        order_type="limit",
        mode="paper",
    )
    await session.commit()

    filled = await oms.submit(order, sample_market.external_id)
    assert filled.status == OrderState.FILLED
    assert float(filled.avg_fill_price) == 0.55


# --- live + idempotency --------------------------------------------------- #

class _FakeAdapter:
    """Records every call; raises on the first N attempts then succeeds."""

    def __init__(self, fail_first: int = 0, *, status: str = "filled") -> None:
        self.calls: list[dict] = []
        self.fail_first = fail_first
        self.status = status

    async def place_order(self, **kwargs):
        self.calls.append(kwargs)
        if len(self.calls) <= self.fail_first:
            raise TimeoutError("network timeout")
        return {
            "external_order_id": "ext_123",
            "status": self.status,
            "filled_quantity": kwargs["quantity"],
            "avg_fill_price": kwargs["price"],
            "fees": 0.0,
        }


@pytest.mark.critical
async def test_live_submit_passes_client_order_id_unchanged_on_retry(session, sample_market):
    adapter = _FakeAdapter(fail_first=2)
    oms = OMS(session, adapter, max_submit_retries=3)
    order = await oms.create(
        platform="kalshi",
        market_id=sample_market.id,
        side="buy",
        outcome="yes",
        price=0.42,
        quantity=10,
        order_type="limit",
        mode="live",
    )
    await session.commit()
    coid = order.client_order_id

    filled = await oms.submit(order, sample_market.external_id)
    await session.commit()

    assert filled.status == OrderState.FILLED
    assert len(adapter.calls) == 3
    assert all(c["client_order_id"] == coid for c in adapter.calls)


@pytest.mark.critical
async def test_live_submit_marks_failed_after_max_retries(session, sample_market):
    adapter = _FakeAdapter(fail_first=99)
    oms = OMS(session, adapter, max_submit_retries=3)
    order = await oms.create(
        platform="kalshi",
        market_id=sample_market.id,
        side="buy",
        outcome="yes",
        price=0.42,
        quantity=10,
        order_type="limit",
        mode="live",
    )
    await session.commit()

    with pytest.raises(TimeoutError):
        await oms.submit(order, sample_market.external_id)
    await session.commit()

    assert order.status == OrderState.FAILED


async def test_partially_filled_then_filled_transition(session, sample_market):
    oms = OMS(session)
    order = await oms.create(
        platform="kalshi",
        market_id=sample_market.id,
        side="buy",
        outcome="yes",
        price=0.42,
        quantity=20,
        order_type="limit",
        mode="paper",
    )
    order.status = OrderState.PENDING_ON_EXCHANGE  # set up midstream state
    await oms.mark_partially_filled(order, FillReport(
        external_order_id="ext_x", filled_quantity=10, avg_fill_price=0.42, fees=0.0,
    ))
    assert order.status == OrderState.PARTIALLY_FILLED

    await oms.mark_filled(order, FillReport(
        external_order_id="ext_x", filled_quantity=20, avg_fill_price=0.42, fees=0.0,
    ))
    assert order.status == OrderState.FILLED


async def test_live_submit_without_adapter_fails_closed(session, sample_market):
    oms = OMS(session, adapter=None)
    order = await oms.create(
        platform="kalshi",
        market_id=sample_market.id,
        side="buy",
        outcome="yes",
        price=0.42,
        quantity=10,
        order_type="limit",
        mode="live",
    )
    await session.commit()
    with pytest.raises(RuntimeError):
        await oms.submit(order, sample_market.external_id)
    assert order.status == OrderState.FAILED
