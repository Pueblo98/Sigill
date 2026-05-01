"""Per-market, per-day Kalshi orderbook archive.

Writes append-only JSONL at
``<root>/<platform>/<external_id>/<YYYY-MM-DD>.jsonl``, opening files
lazily on first write of the day for each ``(platform, external_id)``.
A bounded LRU keeps the open file handle count below
``max_open_handles`` so a fleet of subscribed markets doesn't exhaust
file descriptors.

Reader (replay-into-backtester) is out of scope here — the format is
the contract. See ``TODOS.md`` (TODO-9) for the reader follow-up.
"""
from __future__ import annotations

import json
import logging
import os
from collections import OrderedDict
from datetime import datetime, timezone
from typing import IO, Iterable, Optional, Tuple

logger = logging.getLogger(__name__)


_PATH_SAFE = set(
    "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789._-"
)


def _sanitize(name: str) -> str:
    out = "".join(c if c in _PATH_SAFE else "_" for c in name)
    # belt-and-suspenders: collapse any `..` to `__` so a market_id of "..",
    # ".", "../foo", etc. cannot resolve to a parent directory.
    while ".." in out:
        out = out.replace("..", "__")
    return out or "_"


def _coerce_time(raw: object) -> Optional[datetime]:
    if isinstance(raw, datetime):
        return raw if raw.tzinfo else raw.replace(tzinfo=timezone.utc)
    if hasattr(raw, "to_pydatetime"):
        try:
            dt = raw.to_pydatetime()  # type: ignore[union-attr]
            if isinstance(dt, datetime):
                return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)
        except Exception:
            return None
    if isinstance(raw, str):
        try:
            from dateutil.parser import parse  # local import keeps cold-start cheap

            dt = parse(raw)
            return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)
        except Exception:
            return None
    return None


class OrderbookArchive:
    """LRU-bounded writer of per-market, per-day JSONL files.

    Thread/async safety: not concurrent-safe by design. The expected
    caller is a single ``StreamProcessor._flush_once()`` invocation per
    platform, which is awaited sequentially.
    """

    def __init__(self, root_dir: str, max_open_handles: int = 256) -> None:
        if max_open_handles < 1:
            raise ValueError("max_open_handles must be >= 1")
        self.root_dir = root_dir
        self.max_open_handles = max_open_handles
        self._handles: "OrderedDict[Tuple[str, str, str], IO[str]]" = OrderedDict()

    def write_batch(self, platform: str, ticks: Iterable[dict]) -> int:
        """Serialize each tick as one JSON line into its day's file.

        Returns the count successfully written. Malformed ticks (missing
        ``market_id`` or unparseable ``time``) are logged + skipped; one
        bad tick does not abort the batch.
        """
        written = 0
        for tick in ticks:
            external_id = tick.get("market_id") or tick.get("external_id")
            if not external_id:
                logger.warning(
                    "orderbook_archive: tick missing market_id/external_id; skipping: %r",
                    {k: tick.get(k) for k in ("platform", "time", "bid", "ask")},
                )
                continue

            time_val = _coerce_time(tick.get("time"))
            if time_val is None:
                logger.warning(
                    "orderbook_archive: tick missing/unparseable time; skipping: %s",
                    external_id,
                )
                continue

            time_utc = time_val.astimezone(timezone.utc)
            date_str = time_utc.strftime("%Y-%m-%d")

            try:
                handle = self._handle_for(platform, str(external_id), date_str)
            except OSError:
                logger.exception(
                    "orderbook_archive: cannot open file for %s/%s/%s",
                    platform, external_id, date_str,
                )
                continue

            record = dict(tick)
            record.pop("market_id", None)
            record["external_id"] = external_id
            record["platform"] = platform
            record["time"] = time_utc.isoformat()

            try:
                handle.write(json.dumps(record, default=str) + "\n")
                written += 1
            except OSError:
                logger.exception(
                    "orderbook_archive: write failed for %s/%s/%s",
                    platform, external_id, date_str,
                )

        for h in self._handles.values():
            try:
                h.flush()
            except OSError:
                pass
        return written

    def close(self) -> None:
        while self._handles:
            _, handle = self._handles.popitem(last=False)
            try:
                handle.close()
            except OSError:
                pass

    def _handle_for(self, platform: str, external_id: str, date_str: str) -> "IO[str]":
        key = (platform, external_id, date_str)
        if key in self._handles:
            self._handles.move_to_end(key)
            return self._handles[key]

        path_dir = os.path.join(
            self.root_dir, _sanitize(platform), _sanitize(external_id)
        )
        os.makedirs(path_dir, exist_ok=True)
        file_path = os.path.join(path_dir, f"{date_str}.jsonl")
        handle = open(file_path, "a", encoding="utf-8")
        self._handles[key] = handle

        while len(self._handles) > self.max_open_handles:
            _, evicted = self._handles.popitem(last=False)
            try:
                evicted.close()
            except OSError:
                pass

        return handle
