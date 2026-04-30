"""Persist Backtester.run() results into the `backtest_results` table.

Lights up F2's `backtest_results` dashboard widget — it queries this table
ordered by `created_at DESC LIMIT 1`.

The persistence helper is *opt-in*: nothing in the backtest engine calls it
automatically, because batch runs may produce hundreds of intermediate
results and the operator usually only wants to keep the final one. Call
`persist_backtest_result(session, result)` after `Backtester.run()` when
you actually want a row.
"""
from __future__ import annotations

from dataclasses import asdict, is_dataclass
from typing import Any, Optional
from uuid import uuid4

from sqlalchemy.ext.asyncio import AsyncSession

from sigil.backtesting.engine import BacktestResult as InMemoryResult
from sigil.backtesting.metrics import (
    all_metrics,
    max_drawdown,
    sharpe_equivalent,
    win_rate,
)
from sigil.models import BacktestResult


def _config_to_dict(config: Any) -> dict:
    """BacktestConfig has a datetime; asdict() returns those as-is, but JSON
    can't serialize datetime. Stringify them."""
    if is_dataclass(config):
        d = asdict(config)
    elif isinstance(config, dict):
        d = dict(config)
    else:
        d = {}
    for k, v in list(d.items()):
        if hasattr(v, "isoformat"):
            d[k] = v.isoformat()
    return d


async def persist_backtest_result(
    session: AsyncSession,
    result: InMemoryResult,
    *,
    name: Optional[str] = None,
    model_id: Optional[str] = None,
    metrics: Optional[dict] = None,
) -> BacktestResult:
    """Snapshot `result` into the `backtest_results` table.

    `metrics`, if supplied, overrides the values we'd otherwise compute from
    the result. Useful when you've already called `all_metrics(result,
    predictions=...)` and don't want to repeat the work.

    Caller is responsible for committing the session.
    """
    initial = float(result.config.initial_capital)
    final = float(result.final_equity)
    roi = (final - initial) / initial if initial > 0 else 0.0

    if metrics is None:
        metrics = all_metrics(result)

    row = BacktestResult(
        id=uuid4(),
        name=name,
        model_id=model_id,
        config_json=_config_to_dict(result.config),
        initial_capital=initial,
        final_equity=final,
        roi=metrics.get("roi", roi),
        sharpe=metrics.get("sharpe_equivalent", sharpe_equivalent(result.equity_curve)),
        max_drawdown=metrics.get("max_drawdown", max_drawdown(result.equity_curve)),
        win_rate=metrics.get("win_rate", win_rate(result.trades)),
        n_trades=int(metrics.get("n_trades", len(result.trades))),
        brier=metrics.get("brier"),
        log_loss=metrics.get("log_loss"),
        calibration_error=metrics.get("calibration_error"),
    )
    session.add(row)
    await session.flush()
    return row
