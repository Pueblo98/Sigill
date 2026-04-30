"""W2.3.1 — order idempotency under retry (REVIEW-DECISIONS 1E + 3B critical 7).

Lane A's existing OMS test covers "client_order_id stays the same across retries."
This goes one step further by simulating exchange-side dedup: a mock adapter
keyed on `client_order_id`. After 2 timeouts and a successful 3rd attempt, the
exchange should hold *exactly one* logical order with one `external_order_id`,
even though `place_order` was called three times.
"""
from __future__ import annotations

from uuid import uuid4

import httpx
import pytest

from sigil.execution.oms import OMS, OrderState
from sigil.models import Order


class _DedupingExchange:
    """Fake exchange with idempotency-key dedup, like Kalshi.

    First `fail_first` calls raise `httpx.TimeoutException`. Subsequent calls
    are deduped: if `client_order_id` is in `book`, return the prior
    `external_order_id` and never assign a new one. Otherwise mint a new one.
    """

    def __init__(self, fail_first: int) -> None:
        self.calls: list[dict] = []
        self.fail_first = fail_first
        self.book: dict[str, dict] = {}  # client_order_id -> stored exchange row

    async def place_order(self, **kwargs):
        self.calls.append(kwargs)
        if len(self.calls) <= self.fail_first:
            raise httpx.TimeoutException("simulated network timeout")

        coid = kwargs["client_order_id"]
        if coid in self.book:
            return self.book[coid]

        record = {
            "external_order_id": f"ext_{len(self.book) + 1:04d}",
            "status": "filled",
            "filled_quantity": kwargs["quantity"],
            "avg_fill_price": kwargs["price"],
            "fees": 0.0,
        }
        self.book[coid] = record
        return record


pytestmark = pytest.mark.critical


@pytest.mark.asyncio
async def test_retry_after_timeouts_produces_exactly_one_exchange_order(session, sample_market):
    exchange = _DedupingExchange(fail_first=2)
    oms = OMS(session, exchange, max_submit_retries=3)

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
    assert len(exchange.calls) == 3
    assert all(c["client_order_id"] == coid for c in exchange.calls)

    assert len(exchange.book) == 1
    assert coid in exchange.book

    distinct_external_ids = {c["client_order_id"] for c in exchange.calls}
    assert len(distinct_external_ids) == 1


@pytest.mark.asyncio
async def test_resubmit_after_already_succeeded_is_no_op_at_exchange(session, sample_market):
    """Belt-and-suspenders: even if the OMS were re-invoked on the same row,
    the exchange must dedupe on client_order_id and not create a duplicate."""
    exchange = _DedupingExchange(fail_first=0)
    oms = OMS(session, exchange, max_submit_retries=3)

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

    first = await exchange.place_order(
        market_external_id=sample_market.external_id,
        side=order.side,
        outcome=order.outcome,
        price=float(order.price),
        quantity=order.quantity,
        order_type=order.order_type,
        client_order_id=order.client_order_id,
        mode="live",
    )
    second = await exchange.place_order(
        market_external_id=sample_market.external_id,
        side=order.side,
        outcome=order.outcome,
        price=float(order.price),
        quantity=order.quantity,
        order_type=order.order_type,
        client_order_id=order.client_order_id,
        mode="live",
    )

    assert first["external_order_id"] == second["external_order_id"]
    assert len(exchange.book) == 1


@pytest.mark.asyncio
async def test_distinct_orders_get_distinct_external_ids(session, sample_market):
    """Sanity: two different client_order_ids → two exchange records."""
    exchange = _DedupingExchange(fail_first=0)
    oms = OMS(session, exchange, max_submit_retries=3)

    order_a = await oms.create(
        platform="kalshi",
        market_id=sample_market.id,
        side="buy",
        outcome="yes",
        price=0.42,
        quantity=10,
        order_type="limit",
        mode="live",
    )
    order_b = await oms.create(
        platform="kalshi",
        market_id=sample_market.id,
        side="buy",
        outcome="no",
        price=0.55,
        quantity=5,
        order_type="limit",
        mode="live",
    )
    await session.commit()

    await oms.submit(order_a, sample_market.external_id)
    await oms.submit(order_b, sample_market.external_id)
    await session.commit()

    assert len(exchange.book) == 2
    assert order_a.external_order_id != order_b.external_order_id
