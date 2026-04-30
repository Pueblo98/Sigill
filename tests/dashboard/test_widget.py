"""Tests for the Widget base class + registry."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

import pytest
from markupsafe import Markup

from sigil.dashboard.widget import (
    BACKOFF_INTERVALS_MINUTES,
    WIDGET_REGISTRY,
    Widget,
    WidgetBase,
    register_widget,
)
from sigil.dashboard.config import WidgetConfig


def test_register_and_lookup_roundtrip():
    @register_widget("test_roundtrip")
    class _W(WidgetBase):
        async def fetch(self, session: Any) -> int:
            return 1

        def render(self, data: Any) -> Markup:
            return Markup("<x/>")

    try:
        assert WIDGET_REGISTRY["test_roundtrip"] is _W
        assert _W.type == "test_roundtrip"
        instance = _W(WidgetConfig(type="test_roundtrip", cache="1m"))
        assert isinstance(instance, Widget)  # Protocol check
    finally:
        WIDGET_REGISTRY.pop("test_roundtrip", None)


def test_register_widget_rejects_empty_name():
    with pytest.raises(ValueError):
        @register_widget("")  # noqa: F841
        class _Bad(WidgetBase):
            pass


def test_requires_update_first_call_is_true():
    w = _build_dummy_widget(cache="5m")
    assert w.requires_update(datetime.now(timezone.utc)) is True


def test_requires_update_after_success_waits_for_ttl():
    w = _build_dummy_widget(cache="5m")
    t0 = datetime(2026, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
    w.mark_success(now=t0)
    assert w.requires_update(t0) is False
    assert w.requires_update(t0 + timedelta(minutes=1)) is False
    assert w.requires_update(t0 + timedelta(minutes=5)) is True


def test_backoff_progression_caps_at_last_step():
    w = _build_dummy_widget(cache="1m")
    t0 = datetime(2026, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
    err = RuntimeError("boom")

    expected = list(BACKOFF_INTERVALS_MINUTES)
    for step, mins in enumerate(expected):
        w.mark_error(err, now=t0)
        assert w.backoff_step == step
        assert w.next_fetch_at == t0 + timedelta(minutes=mins)

    # Further errors stay capped at the last step.
    w.mark_error(err, now=t0)
    assert w.backoff_step == len(expected) - 1
    assert w.next_fetch_at == t0 + timedelta(minutes=expected[-1])


def test_success_resets_backoff():
    w = _build_dummy_widget(cache="1m")
    t0 = datetime(2026, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
    w.mark_error(RuntimeError("x"), now=t0)
    w.mark_error(RuntimeError("x"), now=t0)
    assert w.backoff_step == 1
    w.mark_success(now=t0)
    assert w.backoff_step == -1
    assert w.last_error is None
    # Next fetch is now governed by cache_ttl, not backoff.
    assert w.next_fetch_at == t0 + timedelta(minutes=1)


def test_render_error_includes_exception_text():
    w = _build_dummy_widget(cache="1m")
    out = w.render_error(ValueError("kaboom"))
    assert "ValueError" in out
    assert "kaboom" in out
    assert 'class="widget-error"' in out


def test_render_empty_default_message():
    w = _build_dummy_widget(cache="1m")
    out = w.render_empty()
    assert "No data yet." in out
    assert "widget-empty" in out


def test_invalid_ttl_raises_at_construction():
    with pytest.raises(ValueError):
        _build_dummy_widget(cache="not-a-ttl")


# ----------------------------------------------------------------------
# helpers
# ----------------------------------------------------------------------


class _Dummy(WidgetBase):
    type = "_dummy_for_tests"

    async def fetch(self, session: Any) -> int:
        return 0

    def render(self, data: Any) -> Markup:
        return Markup("<x/>")


def _build_dummy_widget(*, cache: str) -> _Dummy:
    return _Dummy(WidgetConfig(type="_dummy_for_tests", cache=cache))
