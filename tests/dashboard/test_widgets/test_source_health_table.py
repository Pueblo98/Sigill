"""Tests for the source_health_table widget."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from sigil.dashboard.widgets.source_health_table import (
    SourceHealthTableConfig,
    SourceHealthTableWidget,
)
from sigil.models import SourceHealth


def _make_widget() -> SourceHealthTableWidget:
    return SourceHealthTableWidget(
        SourceHealthTableConfig(type="source_health_table", cache="30s")
    )


@pytest.mark.asyncio
async def test_empty_state(session):
    w = _make_widget()
    data = await w.fetch(session)
    assert data == []
    assert "No source health checks in 24h." in w.render(data)


@pytest.mark.asyncio
async def test_old_rows_excluded(session):
    long_ago = datetime.now(timezone.utc) - timedelta(hours=48)
    session.add(
        SourceHealth(
            check_time=long_ago,
            source_name="kalshi",
            status="ok",
            latency_ms=100,
        )
    )
    await session.commit()

    w = _make_widget()
    data = await w.fetch(session)
    assert data == []


@pytest.mark.asyncio
async def test_aggregates_per_source(session):
    now = datetime.now(timezone.utc)
    session.add_all(
        [
            SourceHealth(
                check_time=now - timedelta(hours=1),
                source_name="kalshi",
                status="ok",
                latency_ms=120,
            ),
            SourceHealth(
                check_time=now - timedelta(hours=2),
                source_name="kalshi",
                status="degraded",
                latency_ms=600,
                error_message="timeout",
            ),
            SourceHealth(
                check_time=now - timedelta(hours=3),
                source_name="kalshi",
                status="ok",
                latency_ms=180,
            ),
            SourceHealth(
                check_time=now - timedelta(minutes=10),
                source_name="polymarket",
                status="ok",
                latency_ms=80,
            ),
        ]
    )
    await session.commit()

    w = _make_widget()
    data = await w.fetch(session)
    assert [r.source_name for r in data] == ["kalshi", "polymarket"]

    kalshi = data[0]
    assert kalshi.latest_status == "ok"
    assert kalshi.error_count_24h == 1
    assert kalshi.p50_latency_ms is not None
    assert kalshi.p95_latency_ms is not None
    assert kalshi.p50_latency_ms <= kalshi.p95_latency_ms

    out = w.render(data)
    assert 'data-widget-type="source_health_table"' in out
    assert "kalshi" in out
    assert "polymarket" in out


@pytest.mark.asyncio
async def test_status_color_class_applied(session):
    now = datetime.now(timezone.utc)
    session.add(
        SourceHealth(
            check_time=now,
            source_name="bad",
            status="error",
            latency_ms=10,
        )
    )
    await session.commit()
    w = _make_widget()
    data = await w.fetch(session)
    out = w.render(data)
    assert 'class="negative"' in out
