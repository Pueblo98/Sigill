"""Tests for parse_ttl + WidgetCache."""

from __future__ import annotations

import time
from datetime import timedelta

import pytest

from sigil.dashboard.cache import WidgetCache, parse_ttl


@pytest.mark.parametrize(
    ("spec", "expected"),
    [
        ("30s", timedelta(seconds=30)),
        ("1m", timedelta(minutes=1)),
        ("5m", timedelta(minutes=5)),
        ("1h", timedelta(hours=1)),
        ("2d", timedelta(days=2)),
        ("hourly", timedelta(hours=1)),
        ("HOURLY", timedelta(hours=1)),
        ("daily", timedelta(days=1)),
        ("  10s  ", timedelta(seconds=10)),
    ],
)
def test_parse_ttl_happy_path(spec, expected):
    assert parse_ttl(spec) == expected


@pytest.mark.parametrize("spec", ["", "  ", "five-minutes", "1y", "0s", "-1m", "m1", "5", "5 m m"])
def test_parse_ttl_invalid(spec):
    with pytest.raises(ValueError):
        parse_ttl(spec)


def test_parse_ttl_non_string():
    with pytest.raises(ValueError):
        parse_ttl(None)  # type: ignore[arg-type]


def test_widget_cache_set_get():
    cache = WidgetCache(default_ttl=timedelta(seconds=60))
    cache.set(("market_list", "k1"), [1, 2, 3])
    entry = cache.get(("market_list", "k1"))
    assert entry is not None
    assert entry.value == [1, 2, 3]
    assert entry.is_error is False


def test_widget_cache_miss_returns_none():
    cache = WidgetCache()
    assert cache.get(("nope", "x")) is None


def test_widget_cache_invalidate():
    cache = WidgetCache()
    key = ("w", "k")
    cache.set(key, "hello")
    assert cache.get(key) is not None
    cache.invalidate(key)
    assert cache.get(key) is None


def test_widget_cache_clear():
    cache = WidgetCache()
    cache.set(("a", "1"), 1)
    cache.set(("b", "2"), 2)
    assert len(cache) == 2
    cache.clear()
    assert len(cache) == 0


def test_widget_cache_ttl_expiry():
    cache = WidgetCache(default_ttl=timedelta(milliseconds=20))
    key = ("w", "k")
    cache.set(key, "x")
    assert cache.get(key) is not None
    time.sleep(0.05)
    assert cache.get(key) is None


def test_widget_cache_error_marker():
    cache = WidgetCache()
    cache.set(("w", "k"), "stale", is_error=True)
    entry = cache.get(("w", "k"))
    assert entry is not None
    assert entry.is_error is True
