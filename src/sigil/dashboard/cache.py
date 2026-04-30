"""TTL-cache wrapper + TTL spec parser for the dashboard."""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import timedelta
from threading import RLock
from typing import Any, Optional, Tuple

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
    """Per-key TTL cache for widget render data.

    Keys are `(widget_type, cache_key)` tuples; values are arbitrary Python
    objects (typically the result of `Widget.fetch`). The TTL is enforced at
    the cache level (cachetools.TTLCache) and again at the widget level via
    `requires_update`.

    Cap of 4096 entries is generous for ~12 widgets x small key cardinality;
    the LRU eviction inside TTLCache prevents unbounded growth.
    """

    def __init__(self, default_ttl: timedelta = timedelta(minutes=5), maxsize: int = 4096):
        self._lock = RLock()
        self._default_ttl_seconds = default_ttl.total_seconds()
        # cachetools.TTLCache uses a single TTL for all entries. Per-widget TTLs
        # are enforced by the orchestrator's `requires_update` check before it
        # decides to refetch — this cache is the storage tier; expiry just bounds
        # memory.
        self._cache: TTLCache = TTLCache(maxsize=maxsize, ttl=self._default_ttl_seconds)

    def get(self, key: CacheKey) -> Optional[CacheEntry]:
        with self._lock:
            return self._cache.get(key)

    def set(self, key: CacheKey, value: Any, *, is_error: bool = False) -> None:
        with self._lock:
            self._cache[key] = CacheEntry(value=value, is_error=is_error)

    def invalidate(self, key: CacheKey) -> None:
        with self._lock:
            self._cache.pop(key, None)

    def clear(self) -> None:
        with self._lock:
            self._cache.clear()

    def __len__(self) -> int:
        with self._lock:
            return len(self._cache)

    def __contains__(self, key: CacheKey) -> bool:
        with self._lock:
            return key in self._cache
