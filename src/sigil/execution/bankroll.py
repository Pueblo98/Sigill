"""Bankroll snapshot writer (W2.2(b) / REVIEW-DECISIONS 2F).

The drawdown circuit breaker reads `BankrollSnapshot` history to compute
peak-in-window vs. current equity. Without periodic snapshots, the breaker
is permanently in INACTIVE because no rows exist.

This module computes a snapshot from current Position state and writes one
row per `mode`. Equity is derived as:

    equity = BANKROLL_INITIAL
           + sum(realized_pnl over all positions in mode)
           + sum(unrealized_pnl over open positions in mode)

Settled-trade counts come from closed Positions; the 30-day window uses
`Position.closed_at`.
"""
from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from typing import Optional

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from sigil.config import config
from sigil.models import BankrollSnapshot, Position

logger = logging.getLogger(__name__)


async def snapshot_bankroll(
    session: AsyncSession,
    mode: str,
    *,
    initial_bankroll: Optional[float] = None,
    now: Optional[datetime] = None,
) -> BankrollSnapshot:
    """Compute and persist a single BankrollSnapshot row for `mode`."""
    base_bankroll = float(initial_bankroll if initial_bankroll is not None else config.BANKROLL_INITIAL)
    snapshot_time = now or datetime.now(timezone.utc)
    window_start = snapshot_time - timedelta(days=config.DRAWDOWN_WINDOW_DAYS)

    realized_total_q = select(func.coalesce(func.sum(Position.realized_pnl), 0.0)).where(Position.mode == mode)
    unrealized_total_q = (
        select(func.coalesce(func.sum(Position.unrealized_pnl), 0.0))
        .where(Position.mode == mode)
        .where(Position.status == "open")
    )
    settled_total_q = (
        select(func.count())
        .select_from(Position)
        .where(Position.mode == mode)
        .where(Position.status == "closed")
    )
    settled_window_q = (
        select(func.count())
        .select_from(Position)
        .where(Position.mode == mode)
        .where(Position.status == "closed")
        .where(Position.closed_at >= window_start)
    )

    realized_total = float((await session.execute(realized_total_q)).scalar_one() or 0.0)
    unrealized_total = float((await session.execute(unrealized_total_q)).scalar_one() or 0.0)
    settled_total = int((await session.execute(settled_total_q)).scalar_one() or 0)
    settled_in_window = int((await session.execute(settled_window_q)).scalar_one() or 0)

    equity = base_bankroll + realized_total + unrealized_total

    snap = BankrollSnapshot(
        time=snapshot_time,
        mode=mode,
        equity=equity,
        realized_pnl_total=realized_total,
        unrealized_pnl_total=unrealized_total,
        settled_trades_total=settled_total,
        settled_trades_30d=settled_in_window,
    )
    session.add(snap)
    await session.commit()
    logger.info(
        "bankroll snapshot mode=%s equity=%.2f realized=%.2f unrealized=%.2f settled_total=%d settled_30d=%d",
        mode,
        equity,
        realized_total,
        unrealized_total,
        settled_total,
        settled_in_window,
    )
    return snap
