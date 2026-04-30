"""Order Management System.

Implements the state machine from PRD section 5.1:

    CREATED -> SUBMITTED -> PENDING_ON_EXCHANGE
        PENDING_ON_EXCHANGE -> FILLED | PARTIALLY_FILLED | CANCELLED | REJECTED
        PARTIALLY_FILLED    -> FILLED | CANCELLED
        SUBMITTED           -> FAILED (network/API error)

Idempotency (REVIEW-DECISIONS 1E): every Order carries a client-generated
`client_order_id = f"sigil_{uuid4()}"`; we pass it to the exchange and reuse it
on retry so the exchange dedupes server-side.

Mode gating (REVIEW-DECISIONS 2E): paper orders short-circuit at submit time
and simulate against the latest `MarketPrice`; live orders go to the adapter.
"""
from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Optional, Protocol
from uuid import UUID, uuid4

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from sigil.models import MarketPrice, Order, Position

logger = logging.getLogger(__name__)


# --- States --------------------------------------------------------------- #

class OrderState:
    CREATED = "created"
    SUBMITTED = "submitted"
    PENDING_ON_EXCHANGE = "pending_on_exchange"
    PARTIALLY_FILLED = "partially_filled"
    FILLED = "filled"
    REJECTED = "rejected"
    CANCELLED = "cancelled"
    FAILED = "failed"


# Valid transitions: from -> {to,...}
_TRANSITIONS: dict[str, set[str]] = {
    OrderState.CREATED: {OrderState.SUBMITTED, OrderState.FAILED, OrderState.CANCELLED},
    OrderState.SUBMITTED: {
        OrderState.PENDING_ON_EXCHANGE,
        OrderState.FILLED,
        OrderState.PARTIALLY_FILLED,
        OrderState.REJECTED,
        OrderState.FAILED,
        OrderState.CANCELLED,
    },
    OrderState.PENDING_ON_EXCHANGE: {
        OrderState.FILLED,
        OrderState.PARTIALLY_FILLED,
        OrderState.REJECTED,
        OrderState.CANCELLED,
        OrderState.FAILED,
    },
    OrderState.PARTIALLY_FILLED: {OrderState.FILLED, OrderState.CANCELLED},
    OrderState.FILLED: set(),
    OrderState.REJECTED: set(),
    OrderState.CANCELLED: set(),
    OrderState.FAILED: set(),
}

TERMINAL_STATES = {
    OrderState.FILLED,
    OrderState.REJECTED,
    OrderState.CANCELLED,
    OrderState.FAILED,
}


class IllegalStateTransition(RuntimeError):
    def __init__(self, current: str, target: str):
        super().__init__(f"illegal transition {current} -> {target}")
        self.current = current
        self.target = target


def assert_transition(current: str, target: str) -> None:
    allowed = _TRANSITIONS.get(current, set())
    if target not in allowed:
        raise IllegalStateTransition(current, target)


# --- Adapter contract ----------------------------------------------------- #

class ExchangeOrderAdapter(Protocol):
    """Subset of the exchange adapter the OMS needs.

    Implementations MUST treat `client_order_id` as the idempotency key and
    return the same external_order_id on retry.
    """

    async def place_order(
        self,
        *,
        market_external_id: str,
        side: str,
        outcome: str,
        price: float,
        quantity: int,
        order_type: str,
        client_order_id: str,
        mode: str,
    ) -> dict:
        ...


@dataclass
class FillReport:
    external_order_id: Optional[str]
    filled_quantity: int
    avg_fill_price: Optional[float]
    fees: float = 0.0
    status: str = OrderState.FILLED


# --- OMS ------------------------------------------------------------------ #

def new_client_order_id() -> str:
    return f"sigil_{uuid4()}"


class OMS:
    """Stateless coordinator: takes a session, an order, and (for live) an
    exchange adapter. All state transitions go through `transition()` so the
    state machine is enforced in one place.
    """

    def __init__(
        self,
        session: AsyncSession,
        adapter: Optional[ExchangeOrderAdapter] = None,
        *,
        max_submit_retries: int = 3,
        retry_backoff_seconds: float = 0.0,
    ) -> None:
        self.session = session
        self.adapter = adapter
        self.max_submit_retries = max_submit_retries
        self.retry_backoff_seconds = retry_backoff_seconds

    # --- transitions ------------------------------------------------------ #

    async def transition(self, order: Order, target: str) -> Order:
        assert_transition(order.status, target)
        order.status = target
        order.updated_at = datetime.now(timezone.utc)
        self.session.add(order)
        return order

    # --- create / submit -------------------------------------------------- #

    async def create(
        self,
        *,
        platform: str,
        market_id: UUID,
        side: str,
        outcome: str,
        price: float,
        quantity: int,
        order_type: str,
        mode: str,
        prediction_id: Optional[UUID] = None,
        edge_at_entry: Optional[float] = None,
        client_order_id: Optional[str] = None,
    ) -> Order:
        order = Order(
            id=uuid4(),
            client_order_id=client_order_id or new_client_order_id(),
            platform=platform,
            market_id=market_id,
            prediction_id=prediction_id,
            mode=mode,
            side=side,
            outcome=outcome,
            order_type=order_type,
            price=price,
            quantity=quantity,
            filled_quantity=0,
            fees=0,
            edge_at_entry=edge_at_entry,
            status=OrderState.CREATED,
        )
        self.session.add(order)
        return order

    async def submit(self, order: Order, market_external_id: str) -> Order:
        """Submit to exchange (live) or simulate (paper).

        Idempotent: retries on transient failures reuse the same
        `client_order_id`. Caller is responsible for committing the session.
        """
        await self.transition(order, OrderState.SUBMITTED)

        if order.mode == "paper":
            return await self._simulate_paper_fill(order)

        if self.adapter is None:
            await self.transition(order, OrderState.FAILED)
            raise RuntimeError("live order requires exchange adapter")

        last_error: Optional[Exception] = None
        for attempt in range(1, self.max_submit_retries + 1):
            try:
                result = await self.adapter.place_order(
                    market_external_id=market_external_id,
                    side=order.side,
                    outcome=order.outcome,
                    price=float(order.price),
                    quantity=order.quantity,
                    order_type=order.order_type,
                    client_order_id=order.client_order_id,
                    mode=order.mode,
                )
                order.external_order_id = result.get("external_order_id")
                exchange_status = result.get("status", OrderState.PENDING_ON_EXCHANGE)
                await self.transition(order, _normalise(exchange_status))
                if exchange_status in (OrderState.FILLED, OrderState.PARTIALLY_FILLED):
                    order.filled_quantity = int(result.get("filled_quantity", order.quantity))
                    order.avg_fill_price = float(result.get("avg_fill_price", order.price))
                    order.fees = float(result.get("fees", 0.0))
                return order
            except Exception as exc:  # noqa: BLE001 — retried below
                last_error = exc
                logger.warning(
                    "submit attempt %d/%d failed for %s: %s",
                    attempt, self.max_submit_retries, order.client_order_id, exc,
                )
                if attempt < self.max_submit_retries and self.retry_backoff_seconds:
                    await asyncio.sleep(self.retry_backoff_seconds)

        await self.transition(order, OrderState.FAILED)
        assert last_error is not None
        raise last_error

    async def _simulate_paper_fill(self, order: Order) -> Order:
        latest = await self.session.execute(
            select(MarketPrice)
            .where(MarketPrice.market_id == order.market_id)
            .order_by(MarketPrice.time.desc())
            .limit(1)
        )
        price_row = latest.scalar_one_or_none()
        fill_price: float
        if price_row is None:
            fill_price = float(order.price)
        else:
            if order.side == "buy":
                fill_price = float(price_row.ask or price_row.last_price or order.price)
            else:
                fill_price = float(price_row.bid or price_row.last_price or order.price)

        await self.transition(order, OrderState.PENDING_ON_EXCHANGE)
        await self.transition(order, OrderState.FILLED)
        order.external_order_id = f"paper_{order.client_order_id}"
        order.filled_quantity = order.quantity
        order.avg_fill_price = fill_price
        order.fees = 0.0
        return order

    # --- explicit lifecycle methods -------------------------------------- #

    async def mark_pending(self, order: Order) -> Order:
        return await self.transition(order, OrderState.PENDING_ON_EXCHANGE)

    async def mark_filled(self, order: Order, report: FillReport) -> Order:
        await self.transition(order, OrderState.FILLED)
        order.external_order_id = report.external_order_id or order.external_order_id
        order.filled_quantity = report.filled_quantity
        order.avg_fill_price = report.avg_fill_price
        order.fees = report.fees
        return order

    async def mark_partially_filled(self, order: Order, report: FillReport) -> Order:
        await self.transition(order, OrderState.PARTIALLY_FILLED)
        order.external_order_id = report.external_order_id or order.external_order_id
        order.filled_quantity = report.filled_quantity
        order.avg_fill_price = report.avg_fill_price
        order.fees = report.fees
        return order

    async def mark_rejected(self, order: Order, reason: str = "") -> Order:
        if reason:
            logger.info("order %s rejected: %s", order.client_order_id, reason)
        return await self.transition(order, OrderState.REJECTED)

    async def mark_cancelled(self, order: Order) -> Order:
        return await self.transition(order, OrderState.CANCELLED)

    async def mark_failed(self, order: Order, reason: str = "") -> Order:
        if reason:
            logger.warning("order %s failed: %s", order.client_order_id, reason)
        return await self.transition(order, OrderState.FAILED)


def _normalise(status: str) -> str:
    s = status.lower().replace("-", "_")
    aliases = {
        "open": OrderState.PENDING_ON_EXCHANGE,
        "working": OrderState.PENDING_ON_EXCHANGE,
        "pending": OrderState.PENDING_ON_EXCHANGE,
        "partial": OrderState.PARTIALLY_FILLED,
    }
    return aliases.get(s, s)
