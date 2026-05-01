"""Tests for the bankroll_summary widget."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from sigil.config import config as _root_config
from sigil.dashboard.config import WidgetConfig
from sigil.dashboard.widgets.bankroll_summary import (
    BankrollSummaryConfig,
    BankrollSummaryWidget,
)
from sigil.models import BankrollSnapshot


def _make_widget(mode: str = "paper") -> BankrollSummaryWidget:
    cfg = BankrollSummaryConfig(type="bankroll_summary", cache="1m", mode=mode)
    return BankrollSummaryWidget(cfg)


@pytest.mark.asyncio
async def test_empty_state(session):
    w = _make_widget()
    data = await w.fetch(session)
    assert data is None
    out = w.render(data)
    assert "No bankroll snapshot yet." in out


@pytest.mark.asyncio
async def test_returns_latest_snapshot(session):
    now = datetime.now(timezone.utc)
    session.add_all(
        [
            BankrollSnapshot(
                time=now - timedelta(hours=1),
                mode="paper",
                equity=4800.0,
                realized_pnl_total=-200.0,
                unrealized_pnl_total=0.0,
                settled_trades_total=10,
                settled_trades_30d=5,
            ),
            BankrollSnapshot(
                time=now,
                mode="paper",
                equity=5500.0,
                realized_pnl_total=400.0,
                unrealized_pnl_total=100.0,
                settled_trades_total=12,
                settled_trades_30d=6,
            ),
        ]
    )
    await session.commit()

    w = _make_widget("paper")
    data = await w.fetch(session)
    assert data is not None
    assert data.equity == 5500.0
    assert data.realized_pnl == 400.0
    assert data.unrealized_pnl == 100.0
    expected_roi = (5500.0 - _root_config.BANKROLL_INITIAL) / _root_config.BANKROLL_INITIAL * 100.0
    assert data.roi_pct == pytest.approx(expected_roi)
    assert data.settled_trades_total == 12

    out = w.render(data)
    assert "$5,500.00" in out
    assert f"{expected_roi:+.2f}%" in out
    assert "12" in out


@pytest.mark.asyncio
async def test_filters_by_mode(session):
    now = datetime.now(timezone.utc)
    session.add_all(
        [
            BankrollSnapshot(
                time=now,
                mode="paper",
                equity=1000.0,
                realized_pnl_total=0.0,
                unrealized_pnl_total=0.0,
                settled_trades_total=0,
                settled_trades_30d=0,
            ),
            BankrollSnapshot(
                time=now,
                mode="live",
                equity=2000.0,
                realized_pnl_total=0.0,
                unrealized_pnl_total=0.0,
                settled_trades_total=0,
                settled_trades_30d=0,
            ),
        ]
    )
    await session.commit()

    w = _make_widget("live")
    data = await w.fetch(session)
    assert data is not None
    assert data.equity == 2000.0
    assert data.mode == "live"


def test_cache_key_includes_mode():
    w_paper = _make_widget("paper")
    w_live = _make_widget("live")
    assert w_paper.cache_key() != w_live.cache_key()
