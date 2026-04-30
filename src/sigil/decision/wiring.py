"""Decision-engine ↔ OMS wiring (W2.2(a)).

The DecisionEngine takes an `oms_submit` callable so its tests can stay
implementation-agnostic. In production we want the callable to actually
construct and submit a real `Order` via Lane A's `OMS`. This module supplies
that adapter.

The adapter does the following per call:

  1. Loads the Prediction row (for `predicted_prob`, `confidence`,
     `market_price_at_prediction`) — the engine only passes `prediction_id`.
  2. Loads the Market row to get `external_id` for the exchange call.
  3. Falls back to the latest `MarketPrice` if the prediction didn't snapshot
     a price.
  4. Kelly-sizes against a caller-supplied bankroll, applying the engine's
     drawdown `size_multiplier` on top.
  5. Translates dollars → contract count (`int(bet_amount / entry_price)`).
  6. Calls `oms.create()` then `oms.submit()`. Caller is responsible for
     committing the session — mirroring OMS contract.
"""
from __future__ import annotations

import logging
from typing import Any, Awaitable, Callable, Optional
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from sigil.config import config
from sigil.execution.oms import OMS
from sigil.execution.sizing import kelly_size
from sigil.models import Market, MarketPrice, Order, Prediction

logger = logging.getLogger(__name__)


BankrollProvider = Callable[[], Awaitable[float]]


def make_oms_submit(
    oms: OMS,
    bankroll_provider: Optional[BankrollProvider] = None,
    *,
    default_order_type: str = "limit",
) -> Callable[..., Awaitable[Optional[Order]]]:
    """Return an awaitable matching DecisionEngine.oms_submit's expected shape.

    `bankroll_provider`, if supplied, is awaited per call to determine the
    Kelly-sizing bankroll. Defaults to `config.BANKROLL_INITIAL`.
    """

    async def _resolve_bankroll() -> float:
        if bankroll_provider is None:
            return float(config.BANKROLL_INITIAL)
        return float(await bankroll_provider())

    async def submit(**kwargs: Any) -> Optional[Order]:
        session: AsyncSession = kwargs["session"]
        prediction_id: Optional[UUID] = kwargs.get("prediction_id")
        market_id: UUID = kwargs["market_id"]
        platform: str = kwargs["platform"]
        side: str = kwargs.get("side", "buy")
        outcome: str = kwargs.get("outcome", "yes")
        edge_at_entry: float = kwargs.get("edge_at_entry", 0.0)
        size_multiplier: float = kwargs.get("size_multiplier", 1.0)
        mode: str = kwargs.get("mode", config.DEFAULT_MODE)
        order_type: str = kwargs.get("order_type", default_order_type)

        prediction = None
        if prediction_id is not None:
            prediction = await session.get(Prediction, prediction_id)

        market = await session.get(Market, market_id)
        if market is None:
            logger.error("oms_submit: market %s not found; skipping", market_id)
            return None

        entry_price: Optional[float] = None
        if prediction is not None and prediction.market_price_at_prediction is not None:
            entry_price = float(prediction.market_price_at_prediction)
        else:
            latest_price = await session.execute(
                select(MarketPrice)
                .where(MarketPrice.market_id == market_id)
                .order_by(MarketPrice.time.desc())
                .limit(1)
            )
            row = latest_price.scalar_one_or_none()
            if row is not None:
                entry_price = float(row.last_price or row.ask or row.bid or 0.0)

        if not entry_price or entry_price <= 0.0 or entry_price >= 1.0:
            logger.warning(
                "oms_submit: no usable entry price for market %s (got %r); skipping",
                market_id,
                entry_price,
            )
            return None

        p_model = float(prediction.predicted_prob) if prediction is not None else entry_price + edge_at_entry
        confidence = (
            float(prediction.confidence) if prediction is not None and prediction.confidence is not None else 1.0
        )

        bankroll = await _resolve_bankroll()
        sized = kelly_size(
            p_model=p_model,
            p_market=entry_price,
            bankroll=bankroll,
            confidence=confidence,
        )
        bet_amount = sized.bet_amount * float(size_multiplier)
        quantity = int(bet_amount / entry_price)

        if quantity <= 0:
            logger.info(
                "oms_submit: kelly-sized to %d contracts (bet=$%.2f, price=%.3f); skipping",
                quantity,
                bet_amount,
                entry_price,
            )
            return None

        order = await oms.create(
            platform=platform,
            market_id=market_id,
            side=side,
            outcome=outcome,
            price=entry_price,
            quantity=quantity,
            order_type=order_type,
            mode=mode,
            prediction_id=prediction_id,
            edge_at_entry=edge_at_entry,
        )
        await oms.submit(order, market_external_id=market.external_id)
        return order

    return submit
