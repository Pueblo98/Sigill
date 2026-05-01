"""Periodic decision-engine loop.

Polls recent ``Prediction`` rows that have a positive edge but no
associated ``Order``, looks up the latest ``MarketPrice``, and feeds
each through :meth:`DecisionEngine.evaluate`. The engine itself
handles edge thresholds, drawdown gating, Kelly sizing, and OMS
submission — this loop is just the pump.

Wired into ``runner.run_ingestion`` so the system goes from
"predictions in DB" to "orders in DB" without operator intervention.

Skipped predictions:

- ``platform == 'polymarket'`` — read-only per decision 1C; the engine
  rejects these regardless, but we filter early to keep logs clean.
- prediction already has an ``Order`` row (``prediction_id`` FK).
- no ``MarketPrice`` available for the market.
- price is degenerate (0 or 1).
"""
from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timedelta, timezone
from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from sigil.config import config
from sigil.decision.engine import DecisionEngine
from sigil.decision.wiring import make_oms_submit
from sigil.execution.oms import OMS
from sigil.models import Market, MarketPrice, Order, Prediction


logger = logging.getLogger(__name__)


async def run_once(
    session: AsyncSession,
    *,
    lookback_seconds: int = 3600,
    max_predictions: int = 50,
    mode: Optional[str] = None,
) -> int:
    """Run a single pass of the decision loop. Returns count of orders
    submitted (whether accepted or rejected by the engine — see logs).
    """
    mode = mode or config.DEFAULT_MODE
    cutoff = datetime.now(timezone.utc) - timedelta(seconds=lookback_seconds)

    # Predictions with a meaningful edge that haven't already been acted on.
    # MIN_EDGE_KALSHI is the platform threshold the engine uses to gate
    # should_trade; pre-filtering here just keeps the loop tight.
    stmt = (
        select(Prediction)
        .outerjoin(Order, Order.prediction_id == Prediction.id)
        .where(Prediction.created_at >= cutoff)
        .where(Prediction.edge.isnot(None))
        .where(Prediction.edge >= float(config.MIN_EDGE_KALSHI))
        .where(Order.id.is_(None))
        .order_by(Prediction.created_at.desc())
        .limit(max_predictions)
    )
    rows = (await session.execute(stmt)).scalars().all()
    if not rows:
        return 0

    oms = OMS(session=session)
    submit = make_oms_submit(oms)

    async def _stub_drawdown(_session, mode="paper"):
        # The runner doesn't have a drawdown_state_fn wired yet; the
        # engine's default uses a real state lookup. Pass through to
        # the engine's default rather than stubbing.
        from sigil.decision.drawdown import current_state
        return await current_state(_session, mode=mode)

    engine = DecisionEngine(oms_submit=submit, drawdown_state_fn=_stub_drawdown, mode=mode)

    n_evaluated = 0
    for prediction in rows:
        market = await session.get(Market, prediction.market_id)
        if market is None:
            continue
        if (market.platform or "").lower() == "polymarket":
            # Display-only per decision 1C. Engine rejects these too, but
            # filtering here avoids creating polymarket Orders we'd never
            # ship anyway.
            continue

        latest_price = (await session.execute(
            select(MarketPrice)
            .where(MarketPrice.market_id == prediction.market_id)
            .order_by(MarketPrice.time.desc())
            .limit(1)
        )).scalar_one_or_none()
        if latest_price is None:
            continue
        market_price = (
            float(latest_price.last_price)
            if latest_price.last_price is not None
            else (
                float(latest_price.ask)
                if latest_price.ask is not None
                else float(latest_price.bid) if latest_price.bid is not None
                else 0.0
            )
        )
        if market_price <= 0.0 or market_price >= 1.0:
            continue

        try:
            result = await engine.evaluate(
                session=session,
                prediction=prediction,
                market_price=market_price,
                platform=market.platform,
                market_id=market.id,
                side="buy",
                outcome="yes",
            )
        except Exception:
            logger.exception(
                "decision_loop: evaluate failed for prediction %s", prediction.id
            )
            continue

        n_evaluated += 1
        if result.accepted:
            logger.info(
                "decision_loop accepted: market=%s edge=%.3f weighted=%.3f size=%.2f",
                market.external_id, result.edge, result.weighted_edge, result.size_multiplier,
            )
        else:
            logger.debug(
                "decision_loop rejected (%s): market=%s edge=%.3f",
                result.reason, market.external_id, result.edge,
            )

    await session.commit()
    return n_evaluated


async def run_decision_loop(
    session_factory: async_sessionmaker,
    *,
    interval_seconds: Optional[int] = None,
) -> None:
    """Forever-loop wrapper. Cancellation propagates from
    ``asyncio.gather`` in ``run_ingestion``. Sleeps a few seconds before
    the first iteration so the spread_arb signal has a chance to write
    Predictions worth acting on.
    """
    await asyncio.sleep(7)
    interval = max(15, int(interval_seconds or config.DECISION_LOOP_INTERVAL_SECONDS))
    logger.info("decision_loop started (interval=%ds, mode=%s)", interval, config.DEFAULT_MODE)
    while True:
        try:
            async with session_factory() as session:
                n = await run_once(session)
            if n:
                logger.info("decision_loop: evaluated %d prediction(s)", n)
        except Exception:
            logger.exception("decision_loop iteration failed")
        await asyncio.sleep(interval)
