"""Tests for the error_log widget."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from sigil.dashboard.widgets.error_log import ErrorLogConfig, ErrorLogWidget
from sigil.models import SourceHealth


def _make_widget(limit: int = 100) -> ErrorLogWidget:
    return ErrorLogWidget(ErrorLogConfig(type="error_log", cache="1m", limit=limit))


@pytest.mark.asyncio
async def test_empty_state(session):
    w = _make_widget()
    data = await w.fetch(session)
    assert data == []
    assert "No recent errors." in w.render(data)


@pytest.mark.asyncio
async def test_only_rows_with_error_message(session):
    now = datetime.now(timezone.utc)
    session.add_all(
        [
            SourceHealth(
                check_time=now,
                source_name="x",
                status="ok",
                latency_ms=10,
            ),
            SourceHealth(
                check_time=now - timedelta(minutes=1),
                source_name="x",
                status="error",
                latency_ms=999,
                error_message="connection refused",
            ),
        ]
    )
    await session.commit()

    w = _make_widget()
    data = await w.fetch(session)
    assert len(data) == 1
    assert data[0].source_name == "x"
    assert "connection refused" in data[0].message


@pytest.mark.asyncio
async def test_message_truncation(session):
    now = datetime.now(timezone.utc)
    long_msg = "x" * 500
    session.add(
        SourceHealth(
            check_time=now,
            source_name="x",
            status="error",
            latency_ms=10,
            error_message=long_msg,
        )
    )
    await session.commit()

    w = _make_widget()
    data = await w.fetch(session)
    assert len(data) == 1
    assert len(data[0].message) <= 121  # 120 + ellipsis
    assert data[0].message.endswith("…")


@pytest.mark.asyncio
async def test_limit_respected(session):
    now = datetime.now(timezone.utc)
    session.add_all(
        [
            SourceHealth(
                check_time=now - timedelta(seconds=i),
                source_name=f"src-{i}",
                status="error",
                latency_ms=10,
                error_message=f"err-{i}",
            )
            for i in range(10)
        ]
    )
    await session.commit()

    w = _make_widget(limit=3)
    data = await w.fetch(session)
    assert len(data) == 3


@pytest.mark.asyncio
async def test_renders_with_data_widget_type(session):
    now = datetime.now(timezone.utc)
    session.add(
        SourceHealth(
            check_time=now,
            source_name="kalshi",
            status="error",
            error_message="boom",
        )
    )
    await session.commit()

    w = _make_widget()
    data = await w.fetch(session)
    out = w.render(data)
    assert 'data-widget-type="error_log"' in out
    assert "kalshi" in out
    assert "boom" in out
