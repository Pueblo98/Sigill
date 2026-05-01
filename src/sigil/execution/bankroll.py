"""Bankroll snapshot writer (W2.2(b) / REVIEW-DECISIONS 2F).

The drawdown circuit breaker reads `BankrollSnapshot` history to compute
peak-in-window vs. current equity. Without periodic snapshots, the breaker
is permanently in INACTIVE because no rows exist.

This module computes a snapshot from current Position state and writes one
row per `mode`. Equity is derived as:

    equity = BANKROLL_INITIAL
           + sum(realized_pnl over all positions in mode)
           + sum(unrealized_pnl over open positions in mode)

`snapshot_bankroll` first runs `mark_to_market` so the per-Position
`current_price` and `unrealized_pnl` columns are refreshed from the latest
`MarketPrice` before the aggregate is taken. That guarantees the per-row
view returned by `/api/positions` and the aggregate returned by
`/api/portfolio` always match.

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
from sigil.models import BankrollSnapshot, MarketPrice, Position

logger = logging.getLogger(__name__)


async def mark_to_market(session: AsyncSession, mode: str) -> int:
    """Refresh `current_price` and `unrealized_pnl` for every open Position
    in `mode` from the latest `MarketPrice` for its market.

    Pricing rules:
      - Prefer mid = (bid + ask) / 2 when both legs are present.
      - Fall back to last_price, then bid, then ask.
      - For `outcome == 'no'`, invert: NO_price = 1 - YES_price (the
        ingestion pipeline stores YES-side bid/ask by convention).
      - If no price is available at all, leave the row untouched —
        better stale than zeroed.

    Returns the number of positions actually updated (useful for logging
    and tests).
    """
    open_q = (
        select(Position)
        .where(Position.mode == mode)
        .where(Position.status == "open")
    )
    open_positions = (await session.execute(open_q)).scalars().all()
    if not open_positions:
        return 0

    updated = 0
    for pos in open_positions:
        latest = await session.execute(
            select(MarketPrice)
            .where(MarketPrice.market_id == pos.market_id)
            .order_by(MarketPrice.time.desc())
            .limit(1)
        )
        price_row = latest.scalar_one_or_none()
        if price_row is None:
            continue

        bid = float(price_row.bid) if price_row.bid is not None else None
        ask = float(price_row.ask) if price_row.ask is not None else None
        last = float(price_row.last_price) if price_row.last_price is not None else None

        if bid is not None and ask is not None:
            yes_price = (bid + ask) / 2.0
        elif last is not None:
            yes_price = last
        elif bid is not None:
            yes_price = bid
        elif ask is not None:
            yes_price = ask
        else:
            continue

        current = yes_price if pos.outcome == "yes" else (1.0 - yes_price)
        pos.current_price = current
        pos.unrealized_pnl = float(pos.quantity) * (current - float(pos.avg_entry_price))
        updated += 1

    return updated


async def snapshot_bankroll(
    session: AsyncSession,
    mode: str,
    *,
    initial_bankroll: Optional[float] = None,
    now: Optional[datetime] = None,
) -> BankrollSnapshot:
    """Compute and persist a single BankrollSnapshot row for `mode`.

    Re-marks open positions to market first so the snapshot's
    `unrealized_pnl_total` matches the sum of per-Position
    `unrealized_pnl` values returned by `/api/positions`.
    """
    base_bankroll = float(initial_bankroll if initial_bankroll is not None else config.BANKROLL_INITIAL)
    snapshot_time = now or datetime.now(timezone.utc)
    window_start = snapshot_time - timedelta(days=config.DRAWDOWN_WINDOW_DAYS)

    n_marked = await mark_to_market(session, mode)
    if n_marked:
        logger.debug("mark_to_market mode=%s updated=%d", mode, n_marked)

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
