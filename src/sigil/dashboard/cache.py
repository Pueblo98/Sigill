"""TTL-cache wrapper + TTL spec parser for the dashboard."""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import timedelta
from threading import RLock
from typing import Any, Dict, Optional, Tuple

from cachetools import TTLCache


_TTL_SPEC_RE = re.compile(r"^\s*(\d+)\s*([smhd])\s*$", re.IGNORECASE)

_NAMED_TTLS = {
    "hourly": timedelta(hours=1),
    "daily": timedelta(days=1),
}

_UNIT_TO_TIMEDELTA = {
    "s": lambda n: timedelta(seconds=n),
    "m": lambda n: timedelta(minutes=n),
    "h": lambda n: timedelta(hours=n),
    "d": lambda n: timedelta(days=n),
}


def parse_ttl(spec: str) -> timedelta:
    """Parse a TTL spec from YAML.

    Accepted formats:
      - "30s", "1m", "5m", "1h", "2d"
      - "hourly", "daily" (named aliases)

    Raises ValueError on garbage input.
    """
    if not isinstance(spec, str) or not spec.strip():
        raise ValueError(f"invalid TTL spec: {spec!r}")
    s = spec.strip().lower()
    if s in _NAMED_TTLS:
        return _NAMED_TTLS[s]
    m = _TTL_SPEC_RE.match(s)
    if not m:
        raise ValueError(
            f"invalid TTL spec: {spec!r} (use NNs/m/h/d or 'hourly'/'daily')"
        )
    n = int(m.group(1))
    unit = m.group(2).lower()
    if n <= 0:
        raise ValueError(f"TTL must be positive: {spec!r}")
    return _UNIT_TO_TIMEDELTA[unit](n)


CacheKey = Tuple[str, str]


@dataclass
class CacheEntry:
    """Stored cache value plus minimal stale-while-revalidate metadata."""

    value: Any
    is_error: bool = False


class WidgetCache:
    """Per-widget-type TTL cache for widget render data.

    Keys are `(widget_type, cache_key)` tuples; values are arbitrary Python
    objects (typically the result of `Widget.fetch`).

    Each widget type gets its own underlying `TTLCache` so a 1h widget's
    entries aren't LRU-evicted as fast as a 30s widget's entries (TODO-7).
    The TTL is set on first write per type via `set(..., ttl=...)`; if the
    widget's TTL changes (YAML hot reload), call `invalidate_type` to
    force re-creation with the new TTL.
    """

    def __init__(
        self,
        default_ttl: timedelta = timedelta(minutes=5),
        maxsize_per_type: int = 512,
    ):
        self._lock = RLock()
        self._default_ttl_seconds = default_ttl.total_seconds()
        self._maxsize_per_type = maxsize_per_type
        self._caches: Dict[str, TTLCache] = {}

    def _cache_for(self, widget_type: str, ttl: Optional[timedelta]) -> TTLCache:
        cache = self._caches.get(widget_type)
        if cache is None:
            ttl_seconds = ttl.total_seconds() if ttl is not None else self._default_ttl_seconds
            cache = TTLCache(maxsize=self._maxsize_per_type, ttl=ttl_seconds)
            self._caches[widget_type] = cache
        return cache

    def get(self, key: CacheKey) -> Optional[CacheEntry]:
        with self._lock:
            cache = self._caches.get(key[0])
            if cache is None:
                return None
            return cache.get(key)

    def set(
        self,
        key: CacheKey,
        value: Any,
        *,
        ttl: Optional[timedelta] = None,
        is_error: bool = False,
    ) -> None:
        with self._lock:
            cache = self._cache_for(key[0], ttl)
            cache[key] = CacheEntry(value=value, is_error=is_error)

    def invalidate(self, key: CacheKey) -> None:
        with self._lock:
            cache = self._caches.get(key[0])
            if cache is not None:
                cache.pop(key, None)

    def invalidate_type(self, widget_type: str) -> None:
        """Drop the entire per-type cache. Used on YAML hot reload when a
        widget's `cache_ttl` changes — the next `set` re-creates the cache
        with the new TTL."""
        with self._lock:
            self._caches.pop(widget_type, None)

    def clear(self) -> None:
        with self._lock:
            self._caches.clear()

    def ttl_seconds_for(self, widget_type: str) -> Optional[float]:
        """Inspect the TTL currently in effect for `widget_type`. Returns
        None if no entries have been written for that type yet."""
        with self._lock:
            cache = self._caches.get(widget_type)
            return cache.ttl if cache is not None else None

    def __len__(self) -> int:
        with self._lock:
            return sum(len(c) for c in self._caches.values())

    def __contains__(self, key: CacheKey) -> bool:
        with self._lock:
            cache = self._caches.get(key[0])
            return cache is not None and key in cache
