"""Tests for the backtest_results widget.

The widget reads `BacktestResult` rows via SQLAlchemy ORM. It still keeps an
`OperationalError` fallback for deploys that haven't run the migration yet
— those see the empty state instead of a 500.
"""
from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

import pytest
from sqlalchemy.exc import OperationalError

from sigil.dashboard.widgets.backtest_results import (
    BacktestResultsConfig,
    BacktestResultsWidget,
)
from sigil.models import BacktestResult


def _make_widget() -> BacktestResultsWidget:
    return BacktestResultsWidget(
        BacktestResultsConfig(type="backtest_results", cache="1h")
    )


@pytest.mark.asyncio
async def test_empty_state_when_no_rows(session):
    w = _make_widget()
    data = await w.fetch(session)
    assert data is None
    out = w.render(data)
    assert "No backtest results yet." in out
    assert 'data-widget-type="backtest_results"' in out


@pytest.mark.asyncio
async def test_renders_latest_when_rows_present(session):
    older = datetime(2026, 1, 1, tzinfo=timezone.utc)
    newer = datetime(2026, 4, 30, tzinfo=timezone.utc)
    session.add_all(
        [
            BacktestResult(
                id=uuid4(),
                name="older",
                created_at=older,
                config_json={},
                initial_capital=5000.0,
                final_equity=5100.0,
                roi=0.02,
                sharpe=0.5,
                max_drawdown=0.1,
                win_rate=0.5,
                n_trades=50,
                brier=0.21,
                log_loss=0.5,
                calibration_error=0.04,
            ),
            BacktestResult(
                id=uuid4(),
                name="newer",
                created_at=newer,
                config_json={},
                initial_capital=5000.0,
                final_equity=5500.0,
                roi=0.10,
                sharpe=1.2,
                max_drawdown=0.05,
                win_rate=0.6,
                n_trades=80,
                brier=0.18,
                log_loss=0.45,
                calibration_error=0.03,
            ),
        ]
    )
    await session.commit()

    w = _make_widget()
    data = await w.fetch(session)
    assert data is not None
    assert data.name == "newer"
    assert data.roi == pytest.approx(0.10)
    assert data.n_trades == 80

    out = w.render(data)
    assert "newer" in out
    assert "+10.00%" in out
    assert "80" in out


@pytest.mark.asyncio
async def test_widget_falls_back_to_empty_state_on_operational_error():
    """Production safety: a missing table (deploy ran the app without
    running the migration first) should render the empty state, not 500."""

    class _BrokenSession:
        async def execute(self, *args, **kwargs):
            raise OperationalError("stmt", {}, Exception("no such table: backtest_results"))

    w = _make_widget()
    data = await w.fetch(_BrokenSession())
    assert data is None
    assert "No backtest results yet." in w.render(data)


@pytest.mark.asyncio
async def test_renders_with_null_metric_columns(session):
    """Brier / log_loss / calibration_error are nullable. Render should not
    show "n/a" stubs — just skip them."""
    session.add(
        BacktestResult(
            id=uuid4(),
            name="bare",
            config_json={},
            initial_capital=5000.0,
            final_equity=5050.0,
            roi=0.01,
            n_trades=10,
            # brier/log_loss/calibration_error all None
        )
    )
    await session.commit()

    w = _make_widget()
    data = await w.fetch(session)
    out = w.render(data)
    assert "bare" in out
    assert "Brier" not in out
    assert "Log loss" not in out
    assert "Calibration err." not in out
