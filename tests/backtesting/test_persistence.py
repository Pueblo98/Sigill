"""TODO-8: persist_backtest_result snapshots Backtester output to the DB."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import select

from sigil.backtesting.engine import (
    BacktestConfig,
    BacktestResult as InMemoryResult,
    Trade,
)
from sigil.backtesting.persistence import persist_backtest_result
from sigil.models import BacktestResult


def _result(
    *,
    initial: float = 5000.0,
    final: float = 5500.0,
    n_trades: int = 10,
    n_wins: int = 6,
) -> InMemoryResult:
    config = BacktestConfig(
        start_date=datetime(2026, 1, 1, tzinfo=timezone.utc),
        end_date=datetime(2026, 4, 30, tzinfo=timezone.utc),
        initial_capital=initial,
    )
    base = datetime(2026, 1, 1, tzinfo=timezone.utc)
    trades = [
        Trade(
            timestamp=base + timedelta(days=i),
            market_id=__import__("uuid").uuid4(),
            side="buy",
            outcome="yes",
            quantity=1,
            fill_price=0.5,
            fees=0.0,
            realized_pnl=10.0 if i < n_wins else -5.0,
            market_price_at_entry=0.5,
        )
        for i in range(n_trades)
    ]
    # Linear equity curve from initial to final so metrics.roi matches.
    if n_trades > 0:
        step = (final - initial) / n_trades
        equity_curve = [(base + timedelta(days=i), initial + i * step) for i in range(n_trades + 1)]
    else:
        equity_curve = [(base, initial)]
    return InMemoryResult(
        config=config,
        trades=trades,
        equity_curve=equity_curve,
        final_equity=final,
    )


@pytest.mark.asyncio
async def test_persist_writes_row(session):
    result = _result()
    row = await persist_backtest_result(session, result, name="smoke")
    await session.commit()

    rows = (await session.execute(select(BacktestResult))).scalars().all()
    assert len(rows) == 1
    assert rows[0].id == row.id
    assert rows[0].name == "smoke"
    assert float(rows[0].initial_capital) == pytest.approx(5000.0)
    assert float(rows[0].final_equity) == pytest.approx(5500.0)
    assert float(rows[0].roi) == pytest.approx(0.10)
    assert rows[0].n_trades == 10


@pytest.mark.asyncio
async def test_persist_uses_provided_metrics_dict(session):
    """When the caller pre-computed metrics (e.g. via all_metrics with
    predictions), we should snapshot those values verbatim instead of
    recomputing."""
    result = _result()
    metrics = {
        "roi": 0.42,
        "sharpe_equivalent": 1.7,
        "max_drawdown": 0.08,
        "win_rate": 0.7,
        "n_trades": 99,
        "brier": 0.18,
        "log_loss": 0.45,
        "calibration_error": 0.03,
    }
    await persist_backtest_result(session, result, metrics=metrics)
    await session.commit()

    row = (await session.execute(select(BacktestResult))).scalars().one()
    assert float(row.roi) == pytest.approx(0.42)
    assert float(row.sharpe) == pytest.approx(1.7)
    assert float(row.max_drawdown) == pytest.approx(0.08)
    assert float(row.win_rate) == pytest.approx(0.7)
    assert row.n_trades == 99
    assert float(row.brier) == pytest.approx(0.18)


@pytest.mark.asyncio
async def test_persist_serializes_config_to_json(session):
    """BacktestConfig has datetime fields; the row's config_json should
    be JSON-serializable (datetimes stringified)."""
    result = _result()
    row = await persist_backtest_result(session, result)
    await session.commit()

    cfg = row.config_json
    assert isinstance(cfg, dict)
    assert isinstance(cfg["start_date"], str)
    assert "2026-01-01" in cfg["start_date"]


@pytest.mark.asyncio
async def test_persist_records_optional_fields_as_null(session):
    """If metrics dict doesn't include brier/log_loss, those columns
    should be NULL (not 0.0 or NaN)."""
    result = _result()
    metrics = {"roi": 0.10, "win_rate": 0.6, "n_trades": 10}
    await persist_backtest_result(session, result, metrics=metrics)
    await session.commit()

    row = (await session.execute(select(BacktestResult))).scalars().one()
    assert row.brier is None
    assert row.log_loss is None
    assert row.calibration_error is None


@pytest.mark.asyncio
async def test_persist_associates_model_id(session):
    result = _result()
    await persist_backtest_result(session, result, model_id="elo_v2")
    await session.commit()
    row = (await session.execute(select(BacktestResult))).scalars().one()
    assert row.model_id == "elo_v2"


@pytest.mark.asyncio
async def test_widget_renders_persisted_result(session):
    """End-to-end: persist via helper, render via widget."""
    result = _result(initial=5000.0, final=5500.0)
    await persist_backtest_result(session, result, name="e2e")
    await session.commit()

    from sigil.dashboard.widgets.backtest_results import (
        BacktestResultsConfig,
        BacktestResultsWidget,
    )

    widget = BacktestResultsWidget(
        BacktestResultsConfig(type="backtest_results", cache="1h")
    )
    data = await widget.fetch(session)
    assert data is not None
    assert data.name == "e2e"
    assert data.roi == pytest.approx(0.10)
    out = widget.render(data)
    assert "e2e" in out
    assert "+10.00%" in out
