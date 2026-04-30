"""Backtest metrics: Brier, log loss, calibration, ROI, Sharpe, drawdown,
win rate, average edge captured.

Hand-checked formulas. Critical-path code (REVIEW-DECISIONS.md 3B item 10).
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import TYPE_CHECKING, Any, Iterable, Optional, Sequence

if TYPE_CHECKING:  # pragma: no cover
    from sigil.backtesting.engine import BacktestResult, Trade


@dataclass
class PredictionOutcome:
    """Adapter shape consumed by `all_metrics(predictions=...)`.

    The Lane B `Prediction` ORM row carries `predicted_prob` directly, but the
    realized outcome lives on `Market.settlement_value`. Use
    `prediction_outcomes_from_orm` to convert ORM rows into this shape, or
    build them directly in tests.
    """

    predicted_prob: float
    outcome: int  # 0 or 1


def prediction_outcomes_from_orm(
    predictions: Iterable[Any],
    markets_by_id: Optional[dict] = None,
    *,
    yes_threshold: float = 0.5,
) -> list[PredictionOutcome]:
    """W2.2(g): zip ORM `Prediction` rows with `Market.settlement_value`.

    `predictions` is any iterable of objects with `predicted_prob` and
    `market_id` attributes.

    `markets_by_id` is `{market_id: Market}`; if a Prediction's market is
    absent or unsettled, that prediction is dropped (you can't score an
    unsettled forecast).

    For binary contracts, `settlement_value` of 1.0 / 0.0 maps directly. For
    fractional settlements (rare), threshold at 0.5 unless overridden.
    """
    out: list[PredictionOutcome] = []
    by_id = markets_by_id or {}
    for p in predictions:
        market = by_id.get(getattr(p, "market_id", None))
        if market is None:
            market = getattr(p, "market", None)
        if market is None:
            continue
        sv = getattr(market, "settlement_value", None)
        if sv is None:
            continue
        outcome = 1 if float(sv) >= yes_threshold else 0
        out.append(
            PredictionOutcome(
                predicted_prob=float(p.predicted_prob),
                outcome=outcome,
            )
        )
    return out


_LOG_EPS = 1e-15


def _validate_probs(predictions: Sequence[float], outcomes: Sequence[int]) -> None:
    if len(predictions) != len(outcomes):
        raise ValueError("predictions and outcomes must have the same length")
    if len(predictions) == 0:
        raise ValueError("at least one prediction is required")
    for p in predictions:
        if not 0.0 <= float(p) <= 1.0:
            raise ValueError(f"prediction {p} outside [0,1]")
    for o in outcomes:
        if int(o) not in (0, 1):
            raise ValueError(f"outcome {o} must be 0 or 1")


def brier_score(predictions: Sequence[float], outcomes: Sequence[int]) -> float:
    """MSE between predicted probabilities and binary outcomes.

    Range [0, 1]. 0 = perfect. 0.25 = a 50/50 prediction on any outcome.
    """

    _validate_probs(predictions, outcomes)
    n = len(predictions)
    return sum((float(p) - int(o)) ** 2 for p, o in zip(predictions, outcomes)) / n


def log_loss(predictions: Sequence[float], outcomes: Sequence[int]) -> float:
    """Cross-entropy loss. Predictions are clipped to [eps, 1-eps] to avoid
    log(0). Penalizes confident-wrong harshly."""

    _validate_probs(predictions, outcomes)
    n = len(predictions)
    total = 0.0
    for p, o in zip(predictions, outcomes):
        clipped = min(max(float(p), _LOG_EPS), 1.0 - _LOG_EPS)
        total -= int(o) * math.log(clipped) + (1 - int(o)) * math.log(1.0 - clipped)
    return total / n


def calibration_curve(
    predictions: Sequence[float],
    outcomes: Sequence[int],
    n_bins: int = 10,
) -> tuple[list[float], list[float]]:
    """Returns (mean_predicted_per_bin, observed_freq_per_bin) — for
    plotting calibration / reliability diagrams. Empty bins are skipped.
    """

    _validate_probs(predictions, outcomes)
    if n_bins <= 0:
        raise ValueError("n_bins must be positive")
    bin_preds: list[list[float]] = [[] for _ in range(n_bins)]
    bin_outcomes: list[list[int]] = [[] for _ in range(n_bins)]
    for p, o in zip(predictions, outcomes):
        idx = min(int(float(p) * n_bins), n_bins - 1)
        bin_preds[idx].append(float(p))
        bin_outcomes[idx].append(int(o))
    mean_pred: list[float] = []
    observed: list[float] = []
    for preds, outs in zip(bin_preds, bin_outcomes):
        if not preds:
            continue
        mean_pred.append(sum(preds) / len(preds))
        observed.append(sum(outs) / len(outs))
    return mean_pred, observed


def calibration_error(
    predictions: Sequence[float],
    outcomes: Sequence[int],
    n_bins: int = 10,
) -> float:
    """Mean absolute deviation between mean predicted and observed frequency
    per bin. Returns 0 for a perfectly calibrated forecaster.
    """

    mean_pred, observed = calibration_curve(predictions, outcomes, n_bins)
    if not mean_pred:
        return 0.0
    return sum(abs(p - o) for p, o in zip(mean_pred, observed)) / len(mean_pred)


def roi(
    equity_curve: Sequence[tuple[datetime, float]],
    initial_capital: float,
) -> float:
    """Net P&L / initial capital.

    Per PRD §4.3 we report ROI against deployed capital. Without per-trade
    capital deployment data we approximate with initial capital, which is
    conservative for accounts that never fully deploy.
    """

    if not equity_curve:
        return 0.0
    if initial_capital <= 0:
        raise ValueError("initial_capital must be positive")
    final = float(equity_curve[-1][1])
    return (final - initial_capital) / initial_capital


def sharpe_equivalent(
    equity_curve: Sequence[tuple[datetime, float]],
    periods_per_year: int = 252,
) -> float:
    """Annualized return divided by annualized volatility of period returns.

    Period is the spacing between equity-curve points (treated uniform).
    Returns 0.0 for fewer than two points or zero volatility.
    """

    if len(equity_curve) < 2:
        return 0.0
    returns: list[float] = []
    for prev, curr in zip(equity_curve, equity_curve[1:]):
        prev_eq = float(prev[1])
        curr_eq = float(curr[1])
        if prev_eq <= 0:
            continue
        returns.append(curr_eq / prev_eq - 1.0)
    if len(returns) < 2:
        return 0.0
    mean_r = sum(returns) / len(returns)
    var = sum((r - mean_r) ** 2 for r in returns) / (len(returns) - 1)
    std = math.sqrt(var)
    if std == 0.0:
        return 0.0
    return (mean_r * periods_per_year) / (std * math.sqrt(periods_per_year))


def max_drawdown(equity_curve: Sequence[tuple[datetime, float]]) -> float:
    """Worst peak-to-trough decline as a positive fraction of the prior
    peak. 0.20 == 20% drawdown. Returns 0.0 on monotonic / single-point
    curves."""

    if not equity_curve:
        return 0.0
    peak = float(equity_curve[0][1])
    worst = 0.0
    for _, eq in equity_curve:
        eq_f = float(eq)
        if eq_f > peak:
            peak = eq_f
        if peak > 0:
            dd = (peak - eq_f) / peak
            if dd > worst:
                worst = dd
    return worst


def win_rate(trades: "Iterable[Trade]") -> float:
    settled = [t for t in trades if t.realized_pnl is not None]
    if not settled:
        return 0.0
    wins = sum(1 for t in settled if t.realized_pnl > 0)
    return wins / len(settled)


def avg_edge_captured(trades_with_predictions) -> float:
    """Mean (predicted_prob - market_price_at_entry) over winning settled
    trades. Empty / no-winners returns 0.0.
    """

    edges: list[float] = []
    for trade, prediction in trades_with_predictions:
        if trade.realized_pnl is None or trade.realized_pnl <= 0:
            continue
        if trade.market_price_at_entry is None or prediction is None:
            continue
        predicted = float(getattr(prediction, "predicted_prob", prediction))
        edges.append(predicted - float(trade.market_price_at_entry))
    if not edges:
        return 0.0
    return sum(edges) / len(edges)


def all_metrics(result: "BacktestResult", predictions=None) -> dict:
    """Compute all metrics in one shot. Predictions are optional — without
    them, prediction-dependent metrics (Brier, log loss, calibration,
    avg_edge_captured) are omitted from the output.
    """

    out: dict = {
        "roi": roi(result.equity_curve, result.config.initial_capital),
        "sharpe_equivalent": sharpe_equivalent(result.equity_curve),
        "max_drawdown": max_drawdown(result.equity_curve),
        "win_rate": win_rate(result.trades),
        "final_equity": result.final_equity,
        "n_trades": len(result.trades),
    }

    if predictions:
        probs = [float(p.predicted_prob) for p in predictions]
        outs = [
            int(getattr(p, "outcome", getattr(p, "realized_outcome", None)))
            for p in predictions
            if getattr(p, "outcome", getattr(p, "realized_outcome", None)) is not None
        ]
        if len(probs) == len(outs) and outs:
            out["brier"] = brier_score(probs, outs)
            out["log_loss"] = log_loss(probs, outs)
            out["calibration_error"] = calibration_error(probs, outs)

    return out
