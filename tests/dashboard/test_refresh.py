"""Tests for the RefreshOrchestrator."""

from __future__ import annotations

import asyncio
from datetime import datetime, timedelta, timezone
from typing import Any, List

import pytest
from markupsafe import Markup

from sigil.dashboard.cache import WidgetCache
from sigil.dashboard.config import WidgetConfig
from sigil.dashboard.refresh import RefreshOrchestrator
from sigil.dashboard.widget import WidgetBase


class _TrackingWidget(WidgetBase):
    """Records max-observed concurrency and call count.

    Sleeps a tiny amount inside fetch so multiple inflight fetches actually
    overlap on the event loop.
    """

    type = "_tracking"

    def __init__(self, cache: str = "1m", *, key: str = "k"):
        super().__init__(WidgetConfig(type=self.type, cache=cache))
        self._key = key
        self.calls = 0
        self.in_flight = 0
        self.max_in_flight = 0

    def cache_key(self) -> str:  # type: ignore[override]
        return self._key

    async def fetch(self, session: Any) -> int:
        self.calls += 1
        self.in_flight += 1
        self.max_in_flight = max(self.max_in_flight, self.in_flight)
        try:
            await asyncio.sleep(0.02)
            return self.calls
        finally:
            self.in_flight -= 1

    def render(self, data: Any) -> Markup:
        return Markup(f"<x>{data}</x>")


class _FailingWidget(WidgetBase):
    type = "_failing"

    def __init__(self):
        super().__init__(WidgetConfig(type=self.type, cache="1m"))

    async def fetch(self, session: Any) -> Any:
        raise RuntimeError("boom")

    def render(self, data: Any) -> Markup:
        return Markup("")


@pytest.mark.asyncio
async def test_orchestrator_writes_cache_on_success():
    w = _TrackingWidget()
    cache = WidgetCache()
    orch = RefreshOrchestrator([w], cache)

    await orch.tick()

    entry = cache.get((w.type, w.cache_key()))
    assert entry is not None
    assert entry.value == 1
    assert w.backoff_step == -1


@pytest.mark.asyncio
async def test_orchestrator_skips_widgets_not_due():
    w = _TrackingWidget()
    cache = WidgetCache()
    orch = RefreshOrchestrator([w], cache)

    t0 = datetime.now(timezone.utc)
    await orch.tick(now=t0)
    assert w.calls == 1

    # cache_ttl is 1m, so a tick 30s later must be a no-op.
    await orch.tick(now=t0 + timedelta(seconds=30))
    assert w.calls == 1

    # Past the TTL it fetches again.
    await orch.tick(now=t0 + timedelta(minutes=2))
    assert w.calls == 2


@pytest.mark.asyncio
async def test_orchestrator_applies_backoff_on_exception():
    w = _FailingWidget()
    cache = WidgetCache()
    orch = RefreshOrchestrator([w], cache)
    t0 = datetime(2026, 1, 1, 12, 0, 0, tzinfo=timezone.utc)

    await orch.tick(now=t0)
    # cache untouched
    assert cache.get((w.type, w.cache_key())) is None
    # backoff at step 0 (next retry in 1m)
    assert w.backoff_step == 0
    assert w.next_fetch_at == t0 + timedelta(minutes=1)
    assert isinstance(w.last_error, RuntimeError)


@pytest.mark.asyncio
async def test_orchestrator_respects_concurrency_limit():
    widgets = [_TrackingWidget(key=f"k{i}") for i in range(20)]
    # Tag them so they share a class-level counter via instance attrs is wrong;
    # we look at max_in_flight on each, then take the max across all.
    cache = WidgetCache()
    orch = RefreshOrchestrator(widgets, cache, concurrency=4)

    await orch.tick()

    overall_max = max(w.max_in_flight for w in widgets)
    # Concurrency limit was 4 — across all widgets, no widget alone hits >1
    # (they have unique cache keys), but the SEMAPHORE caps total inflight at
    # 4. We assert via summing instantaneous in_flight elsewhere; instead the
    # cleanest assertion is that no more than 4 fetches were running together
    # at any instant. To measure this we use a shared counter:
    # Re-run with a shared counter.
    shared = {"running": 0, "max": 0}

    class _Shared(WidgetBase):
        type = "_shared"

        def __init__(self, key: str):
            super().__init__(WidgetConfig(type=self.type, cache="1m"))
            self._key = key

        def cache_key(self) -> str:  # type: ignore[override]
            return self._key

        async def fetch(self, session):
            shared["running"] += 1
            shared["max"] = max(shared["max"], shared["running"])
            await asyncio.sleep(0.02)
            shared["running"] -= 1
            return 1

        def render(self, data):
            return Markup("")

    widgets2 = [_Shared(f"s{i}") for i in range(20)]
    orch2 = RefreshOrchestrator(widgets2, WidgetCache(), concurrency=4)
    await orch2.tick()
    assert shared["max"] <= 4
    assert shared["max"] >= 1


@pytest.mark.asyncio
async def test_orchestrator_with_session_factory():
    seen = {"session": None}

    class _Session:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            return None

    class _W(WidgetBase):
        type = "_session_w"

        def __init__(self):
            super().__init__(WidgetConfig(type=self.type, cache="1m"))

        async def fetch(self, session):
            seen["session"] = session
            return "ok"

        def render(self, data):
            return Markup("")

    cache = WidgetCache()
    orch = RefreshOrchestrator([_W()], cache)
    orch._session_factory = _Session  # type: ignore[assignment]
    await orch.tick()

    assert isinstance(seen["session"], _Session)
    assert cache.get(("_session_w", "_session_w")) is not None


@pytest.mark.asyncio
async def test_orchestrator_continues_when_one_widget_fails():
    good = _TrackingWidget(key="good")
    bad = _FailingWidget()
    cache = WidgetCache()
    orch = RefreshOrchestrator([bad, good], cache)

    await orch.tick()

    # Good widget cached despite the bad one raising.
    assert cache.get((good.type, good.cache_key())) is not None
    assert cache.get((bad.type, bad.cache_key())) is None
    assert bad.backoff_step == 0
