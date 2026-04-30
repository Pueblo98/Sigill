"""Tests for the system_health_strip widget."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from sigil.dashboard.widgets.system_health_strip import (
    SystemHealthStripConfig,
    SystemHealthStripWidget,
)
from sigil.models import ReconciliationObservation, SourceHealth


def _make_widget() -> SystemHealthStripWidget:
    return SystemHealthStripWidget(
        SystemHealthStripConfig(type="system_health_strip", cache="1m")
    )


@pytest.mark.asyncio
async def test_empty_state(session):
    w = _make_widget()
    data = await w.fetch(session)
    # No source health rows -> ingestion + scheduler error, reconciliation ok.
    assert data.ingestion.status == "error"
    assert data.scheduler.status == "error"
    assert data.reconciliation.status == "ok"

    out = w.render(data)
    assert "System Health" in out
    assert "Ingestion" in out
    assert "Reconciliation" in out
    assert "Scheduler" in out


@pytest.mark.asyncio
async def test_all_healthy(session):
    now = datetime.now(timezone.utc)
    session.add_all(
        [
            SourceHealth(
                check_time=now,
                source_name="kalshi",
                status="ok",
                latency_ms=100,
                records_fetched=10,
            ),
            SourceHealth(
                check_time=now,
                source_name="polymarket",
                status="ok",
                latency_ms=120,
                records_fetched=20,
            ),
        ]
    )
    await session.commit()

    w = _make_widget()
    data = await w.fetch(session)
    assert data.ingestion.status == "ok"
    assert data.scheduler.status == "ok"
    assert data.reconciliation.status == "ok"


@pytest.mark.asyncio
async def test_one_source_degraded_yields_warning(session, sample_market):
    now = datetime.now(timezone.utc)
    session.add_all(
        [
            SourceHealth(check_time=now, source_name="kalshi", status="ok", latency_ms=100),
            SourceHealth(
                check_time=now,
                source_name="polymarket",
                status="degraded",
                latency_ms=900,
                error_message="timeout",
            ),
        ]
    )
    await session.commit()

    w = _make_widget()
    data = await w.fetch(session)
    assert data.ingestion.status == "warning"
    assert "1/2" in data.ingestion.detail


@pytest.mark.asyncio
async def test_reconciliation_stuck_mismatches(session, sample_market):
    now = datetime.now(timezone.utc)
    for i in range(5):
        session.add(
            ReconciliationObservation(
                observed_at=now - timedelta(minutes=i),
                platform="kalshi",
                market_id=sample_market.id,
                outcome="yes",
                exchange_qty=10,
                local_qty=8,
                is_match=False,
                consecutive_matches=0,
            )
        )
    await session.commit()

    w = _make_widget()
    data = await w.fetch(session)
    assert data.reconciliation.status == "error"


@pytest.mark.asyncio
async def test_old_source_health_treated_as_no_recent_scheduler(session):
    old = datetime.now(timezone.utc) - timedelta(hours=12)
    session.add(
        SourceHealth(check_time=old, source_name="kalshi", status="ok", latency_ms=100)
    )
    await session.commit()

    w = _make_widget()
    data = await w.fetch(session)
    # In-window for ingestion (within 24h) so ingestion is ok.
    assert data.ingestion.status == "ok"
    # Scheduler heartbeat looks at last hour — should be error.
    assert data.scheduler.status == "error"
