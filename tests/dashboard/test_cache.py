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


def test_widget_cache_per_type_ttl_is_recorded_on_first_write():
    cache = WidgetCache()
    cache.set(("fast", "k"), 1, ttl=timedelta(seconds=30))
    cache.set(("slow", "k"), 2, ttl=timedelta(hours=1))
    assert cache.ttl_seconds_for("fast") == pytest.approx(30.0)
    assert cache.ttl_seconds_for("slow") == pytest.approx(3600.0)


def test_widget_cache_per_type_ttl_actually_expires_independently():
    """The whole point of TODO-7: a slow widget's entries don't get
    LRU-evicted as fast as a fast widget's entries."""
    cache = WidgetCache()
    cache.set(("fast", "k"), "fast-val", ttl=timedelta(milliseconds=20))
    cache.set(("slow", "k"), "slow-val", ttl=timedelta(seconds=30))
    time.sleep(0.05)
    assert cache.get(("fast", "k")) is None
    slow_entry = cache.get(("slow", "k"))
    assert slow_entry is not None
    assert slow_entry.value == "slow-val"


def test_widget_cache_invalidate_type_drops_per_type_cache():
    cache = WidgetCache()
    cache.set(("a", "1"), "a1", ttl=timedelta(seconds=10))
    cache.set(("a", "2"), "a2", ttl=timedelta(seconds=10))
    cache.set(("b", "1"), "b1", ttl=timedelta(seconds=10))
    assert len(cache) == 3

    cache.invalidate_type("a")
    assert cache.get(("a", "1")) is None
    assert cache.get(("a", "2")) is None
    assert cache.get(("b", "1")) is not None
    assert cache.ttl_seconds_for("a") is None  # no longer instantiated


def test_widget_cache_default_ttl_when_set_without_explicit_ttl():
    cache = WidgetCache(default_ttl=timedelta(seconds=42))
    cache.set(("widget", "k"), "v")
    assert cache.ttl_seconds_for("widget") == pytest.approx(42.0)


def test_widget_cache_ttl_on_subsequent_write_uses_first_write_value():
    """First write wins for the TTL until invalidate_type is called.
    Documents the current contract — change deliberately, not by accident."""
    cache = WidgetCache()
    cache.set(("widget", "k"), "v1", ttl=timedelta(seconds=30))
    first_ttl = cache.ttl_seconds_for("widget")
    cache.set(("widget", "k"), "v2", ttl=timedelta(hours=1))
    assert cache.ttl_seconds_for("widget") == first_ttl


def test_widget_cache_contains_respects_ttl():
    cache = WidgetCache()
    key = ("w", "k")
    cache.set(key, "x", ttl=timedelta(milliseconds=10))
    assert key in cache
    time.sleep(0.05)
    assert key not in cache
