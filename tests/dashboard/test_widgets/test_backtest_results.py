"""Tests for the backtest_results widget.

Schema gap: there is no ORM ``BacktestResult`` table yet. The widget queries
a hypothetical ``backtest_results`` table directly via raw SQL; on
``OperationalError`` it falls back to the empty state. These tests cover
both:
- the ``no such table`` path (default fixture has no such table)
- the populated path via an ad-hoc table created with raw SQL
"""

from __future__ import annotations

from datetime import datetime, timezone

import pytest
from sqlalchemy import text

from sigil.dashboard.widgets.backtest_results import (
    BacktestResultsConfig,
    BacktestResultsWidget,
)


def _make_widget() -> BacktestResultsWidget:
    return BacktestResultsWidget(
        BacktestResultsConfig(type="backtest_results", cache="1h")
    )


@pytest.mark.asyncio
async def test_empty_state_when_table_missing(session):
    w = _make_widget()
    data = await w.fetch(session)
    assert data is None
    out = w.render(data)
    assert "No backtest results yet." in out
    assert 'data-widget-type="backtest_results"' in out


@pytest.mark.asyncio
async def test_renders_latest_when_table_present(session):
    await session.execute(
        text(
            "CREATE TABLE backtest_results ("
            "id TEXT PRIMARY KEY, "
            "name TEXT, "
            "created_at TIMESTAMP, "
            "initial_capital NUMERIC, "
            "final_equity NUMERIC, "
            "roi NUMERIC, "
            "sharpe NUMERIC, "
            "max_drawdown NUMERIC, "
            "n_trades INTEGER, "
            "brier NUMERIC, "
            "log_loss NUMERIC, "
            "calibration_error NUMERIC"
            ")"
        )
    )
    older = datetime(2026, 1, 1, tzinfo=timezone.utc)
    newer = datetime(2026, 4, 30, tzinfo=timezone.utc)
    await session.execute(
        text(
            "INSERT INTO backtest_results VALUES "
            "('a', 'older', :o, 5000, 5100, 0.02, 0.5, 0.1, 50, 0.21, 0.5, 0.04), "
            "('b', 'newer', :n, 5000, 5500, 0.10, 1.2, 0.05, 80, 0.18, 0.45, 0.03)"
        ),
        {"o": older, "n": newer},
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
async def test_handles_empty_table(session):
    await session.execute(
        text(
            "CREATE TABLE backtest_results ("
            "id TEXT PRIMARY KEY, name TEXT, created_at TIMESTAMP, "
            "initial_capital NUMERIC, final_equity NUMERIC, roi NUMERIC, "
            "sharpe NUMERIC, max_drawdown NUMERIC, n_trades INTEGER, "
            "brier NUMERIC, log_loss NUMERIC, calibration_error NUMERIC"
            ")"
        )
    )
    await session.commit()

    w = _make_widget()
    data = await w.fetch(session)
    assert data is None
    assert "No backtest results yet." in w.render(data)
