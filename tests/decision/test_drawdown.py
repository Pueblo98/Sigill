"""Drawdown circuit-breaker tests.

Marked `critical` — drawdown gate is on the 12 critical paths
(REVIEW-DECISIONS.md 3B + 2F).
"""

from __future__ import annotations

import pytest

from sigil.config import config
from sigil.decision.drawdown import (
    DrawdownState,
    current_state,
    position_size_multiplier,
)


pytestmark = pytest.mark.critical


# ─── position_size_multiplier ─────────────────────────────────────────────────


def test_multiplier_inactive():
    assert position_size_multiplier(DrawdownState.INACTIVE) == 1.0


def test_multiplier_warning_reduces_to_50_pct():
    assert position_size_multiplier(DrawdownState.WARNING) == 0.5


def test_multiplier_halt_zero():
    assert position_size_multiplier(DrawdownState.HALT) == 0.0


def test_multiplier_shutdown_zero():
    assert position_size_multiplier(DrawdownState.SHUTDOWN) == 0.0


# ─── current_state — empty / gated cases ──────────────────────────────────────


@pytest.mark.asyncio
async def test_current_state_no_snapshots_returns_inactive(db_session):
    state = await current_state(db_session, mode="paper")
    assert state == DrawdownState.INACTIVE


@pytest.mark.asyncio
async def test_current_state_below_total_gate_stays_inactive(db_session, make_snapshot):
    # 30% drawdown but only 10 settled trades total — gate must hold.
    db_session.add(make_snapshot(equity=10000, offset_days=10, settled_total=5, settled_30d=2))
    db_session.add(make_snapshot(equity=7000, offset_days=0, settled_total=10, settled_30d=4))
    await db_session.commit()

    state = await current_state(db_session, mode="paper")
    assert state == DrawdownState.INACTIVE


@pytest.mark.asyncio
async def test_current_state_below_window_gate_stays_inactive(db_session, make_snapshot):
    # >=20 settled total but only 4 in the window — gate must hold.
    db_session.add(make_snapshot(equity=10000, offset_days=10, settled_total=21, settled_30d=4))
    db_session.add(make_snapshot(equity=7000, offset_days=0, settled_total=25, settled_30d=4))
    await db_session.commit()

    state = await current_state(db_session, mode="paper")
    assert state == DrawdownState.INACTIVE


# ─── current_state — threshold firing ─────────────────────────────────────────


@pytest.mark.asyncio
async def test_current_state_warning_fires_at_10_pct(db_session, make_snapshot):
    db_session.add(make_snapshot(equity=10000, offset_days=10))
    db_session.add(make_snapshot(equity=8800, offset_days=0))  # 12% drawdown
    await db_session.commit()

    state = await current_state(db_session, mode="paper")
    assert state == DrawdownState.WARNING


@pytest.mark.asyncio
async def test_current_state_halt_fires_at_15_pct(db_session, make_snapshot):
    db_session.add(make_snapshot(equity=10000, offset_days=10))
    db_session.add(make_snapshot(equity=8300, offset_days=0))  # 17% drawdown
    await db_session.commit()

    state = await current_state(db_session, mode="paper")
    assert state == DrawdownState.HALT


@pytest.mark.asyncio
async def test_current_state_shutdown_fires_at_20_pct(db_session, make_snapshot):
    db_session.add(make_snapshot(equity=10000, offset_days=10))
    db_session.add(make_snapshot(equity=7500, offset_days=0))  # 25% drawdown
    await db_session.commit()

    state = await current_state(db_session, mode="paper")
    assert state == DrawdownState.SHUTDOWN


@pytest.mark.asyncio
async def test_current_state_uses_window_peak_not_global_peak(db_session, make_snapshot):
    # Old high outside window should not count.
    db_session.add(make_snapshot(equity=20000, offset_days=config.DRAWDOWN_WINDOW_DAYS + 5))
    db_session.add(make_snapshot(equity=10000, offset_days=20))  # in-window peak
    db_session.add(make_snapshot(equity=9700, offset_days=0))    # 3% drawdown vs window peak
    await db_session.commit()

    state = await current_state(db_session, mode="paper")
    # Drawdown is only 3% relative to in-window peak — under WARNING threshold (10%).
    assert state == DrawdownState.INACTIVE


@pytest.mark.asyncio
async def test_current_state_recovered_returns_inactive(db_session, make_snapshot):
    db_session.add(make_snapshot(equity=10000, offset_days=20))
    db_session.add(make_snapshot(equity=9000, offset_days=10))
    db_session.add(make_snapshot(equity=10500, offset_days=0))  # new ATH; peak=10500
    await db_session.commit()

    state = await current_state(db_session, mode="paper")
    assert state == DrawdownState.INACTIVE


@pytest.mark.asyncio
async def test_current_state_filters_by_mode(db_session, make_snapshot):
    # Live mode is in shutdown territory; paper mode is healthy.
    db_session.add(make_snapshot(equity=10000, mode="live", offset_days=10))
    db_session.add(make_snapshot(equity=7000, mode="live", offset_days=0))   # 30% drop
    db_session.add(make_snapshot(equity=10000, mode="paper", offset_days=10))
    db_session.add(make_snapshot(equity=10100, mode="paper", offset_days=0))
    await db_session.commit()

    paper = await current_state(db_session, mode="paper")
    live = await current_state(db_session, mode="live")
    assert paper == DrawdownState.INACTIVE
    assert live == DrawdownState.SHUTDOWN
