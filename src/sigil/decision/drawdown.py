"""Drawdown circuit breaker.

PRD §5.3 plus REVIEW-DECISIONS.md 2F:

  - Compute drawdown over the latest snapshot vs. the peak inside the window:
        drawdown = (peak_in_window - current) / peak_in_window
  - Three thresholds (config): WARNING, HALT, SHUTDOWN.
  - Min-trade gate: drawdown ONLY fires when:
        settled_trades_total   >= DRAWDOWN_MIN_SETTLED_TOTAL    (20)
        settled_trades_30d     >= DRAWDOWN_MIN_SETTLED_IN_WINDOW (5)
    Below the gate, return INACTIVE regardless of equity moves.
  - Position-size multiplier:
        INACTIVE -> 1.0
        WARNING  -> 0.5  (per PRD §5.3, reduce sizing to 50%)
        HALT     -> 0.0
        SHUTDOWN -> 0.0
"""

from __future__ import annotations

import enum
import logging
from datetime import timedelta
from typing import Any

from sqlalchemy import select

from sigil.config import config
from sigil.models import BankrollSnapshot

logger = logging.getLogger(__name__)


class DrawdownState(enum.Enum):
    INACTIVE = "inactive"
    WARNING = "warning"
    HALT = "halt"
    SHUTDOWN = "shutdown"


_MULTIPLIERS: dict[DrawdownState, float] = {
    DrawdownState.INACTIVE: 1.0,
    DrawdownState.WARNING: 0.5,
    DrawdownState.HALT: 0.0,
    DrawdownState.SHUTDOWN: 0.0,
}


def position_size_multiplier(state: DrawdownState) -> float:
    """Return the bankroll-fraction multiplier for the given state."""
    return _MULTIPLIERS[state]


def _classify(drawdown_pct: float) -> DrawdownState:
    if drawdown_pct >= config.DRAWDOWN_SHUTDOWN_PCT:
        return DrawdownState.SHUTDOWN
    if drawdown_pct >= config.DRAWDOWN_HALT_PCT:
        return DrawdownState.HALT
    if drawdown_pct >= config.DRAWDOWN_WARNING_PCT:
        return DrawdownState.WARNING
    return DrawdownState.INACTIVE


async def current_state(session: Any, mode: str = "paper") -> DrawdownState:
    """Compute the current drawdown state from BankrollSnapshot history.

    Reads the latest snapshot for the gate check, then looks back
    `DRAWDOWN_WINDOW_DAYS` days to find peak equity inside the window.
    """
    latest_q = (
        select(BankrollSnapshot)
        .where(BankrollSnapshot.mode == mode)
        .order_by(BankrollSnapshot.time.desc())
        .limit(1)
    )
    result = await session.execute(latest_q)
    latest = result.scalar_one_or_none()

    if latest is None:
        return DrawdownState.INACTIVE

    if (
        latest.settled_trades_total < config.DRAWDOWN_MIN_SETTLED_TOTAL
        or latest.settled_trades_30d < config.DRAWDOWN_MIN_SETTLED_IN_WINDOW
    ):
        logger.debug(
            "Drawdown gate not met: settled_total=%d/%d, settled_30d=%d/%d",
            latest.settled_trades_total,
            config.DRAWDOWN_MIN_SETTLED_TOTAL,
            latest.settled_trades_30d,
            config.DRAWDOWN_MIN_SETTLED_IN_WINDOW,
        )
        return DrawdownState.INACTIVE

    window_start = latest.time - timedelta(days=config.DRAWDOWN_WINDOW_DAYS)
    window_q = (
        select(BankrollSnapshot)
        .where(BankrollSnapshot.mode == mode)
        .where(BankrollSnapshot.time >= window_start)
    )
    result = await session.execute(window_q)
    window_rows = result.scalars().all()

    peak = max((float(row.equity) for row in window_rows), default=float(latest.equity))
    if peak <= 0:
        return DrawdownState.INACTIVE

    drawdown_pct = (peak - float(latest.equity)) / peak * 100.0
    state = _classify(drawdown_pct)

    if state is not DrawdownState.INACTIVE:
        logger.warning(
            "Drawdown circuit breaker: state=%s drawdown=%.2f%% (peak=%.2f current=%.2f)",
            state.value,
            drawdown_pct,
            peak,
            float(latest.equity),
        )

    return state
