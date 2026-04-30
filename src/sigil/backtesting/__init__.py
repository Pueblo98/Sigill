"""Sigil backtesting framework.

Public API per Lane D scope (REVIEW-DECISIONS.md 3B/3C, PRD §4.3, §4.4).

Conservative fill modeling, deterministic event-driven replay, and full metrics
suite (Brier, log loss, calibration error, ROI, Sharpe-equivalent, max drawdown,
win rate, avg edge captured) plus walk-forward / purged k-fold splitters.
"""

from sigil.backtesting.engine import (
    Backtester,
    BacktestConfig,
    BacktestResult,
    Event,
    PriceTick,
    SettlementEvent,
    Signal,
    Strategy,
    Trade,
)
from sigil.backtesting.execution_model import (
    ConservativeFillModel,
    ExecutionModel,
    Fill,
    Order,
)
from sigil.backtesting.metrics import (
    all_metrics,
    avg_edge_captured,
    brier_score,
    calibration_curve,
    calibration_error,
    log_loss,
    max_drawdown,
    roi,
    sharpe_equivalent,
    win_rate,
)
from sigil.backtesting.portfolio import Portfolio, PositionState
from sigil.backtesting.walkforward import PurgedKFold, WalkForwardSplitter

__all__ = [
    "Backtester",
    "BacktestConfig",
    "BacktestResult",
    "ConservativeFillModel",
    "Event",
    "ExecutionModel",
    "Fill",
    "Order",
    "Portfolio",
    "PositionState",
    "PriceTick",
    "PurgedKFold",
    "SettlementEvent",
    "Signal",
    "Strategy",
    "Trade",
    "WalkForwardSplitter",
    "all_metrics",
    "avg_edge_captured",
    "brier_score",
    "calibration_curve",
    "calibration_error",
    "log_loss",
    "max_drawdown",
    "roi",
    "sharpe_equivalent",
    "win_rate",
]
