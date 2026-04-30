"""TODO-5: settlement subscriber wiring in main.py."""
from __future__ import annotations

import pytest

from sigil import main as orchestrator
from sigil.config import config


def test_settlement_tasks_disabled_by_default():
    """Default deployment (paper-only laptop) must not try to connect to Kalshi."""
    assert config.SETTLEMENT_WS_ENABLED is False
    tasks = orchestrator.build_settlement_tasks()
    assert tasks == []


@pytest.mark.asyncio
async def test_settlement_tasks_enabled_when_flag_set(monkeypatch):
    monkeypatch.setattr(config, "SETTLEMENT_WS_ENABLED", True)
    tasks = orchestrator.build_settlement_tasks()
    try:
        assert len(tasks) == 2
        names = {t.get_name() for t in tasks}
        assert names == {"settlement_ws", "settlement_poll"}
    finally:
        for t in tasks:
            t.cancel()
        for t in tasks:
            try:
                await t
            except BaseException:  # CancelledError is BaseException in 3.8+
                pass


def test_scheduler_registers_bankroll_job():
    scheduler = orchestrator.build_scheduler()
    job_ids = {j.id for j in scheduler.get_jobs()}
    assert "bankroll_snapshot" in job_ids
