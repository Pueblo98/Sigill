"""Tests for the per-market per-day Kalshi orderbook archive (TODO-1)."""
from __future__ import annotations

import json
from datetime import datetime, timezone

import pytest

from sigil.ingestion.orderbook_archive import OrderbookArchive
from sigil.ingestion.runner import StreamProcessor


def _tick(market_id: str, t: datetime, *, bid: float = 0.5, ask: float = 0.5,
          bids=None, asks=None) -> dict:
    return {
        "market_id": market_id,
        "platform": "kalshi",
        "bid": bid,
        "ask": ask,
        "last_price": bid,
        "time": t,
        "volume_24h": None,
        "open_interest": None,
        "source": "exchange_ws",
        "bids": bids if bids is not None else [],
        "asks": asks if asks is not None else [],
    }


def test_writes_single_tick_to_per_day_file(tmp_path):
    archive = OrderbookArchive(str(tmp_path))
    t = datetime(2026, 5, 1, 12, 0, 0, tzinfo=timezone.utc)
    written = archive.write_batch("kalshi", [
        _tick("KAL-A", t, bid=0.4, ask=0.5, bids=[[40, 100]], asks=[[50, 200]]),
    ])
    archive.close()

    assert written == 1
    p = tmp_path / "kalshi" / "KAL-A" / "2026-05-01.jsonl"
    assert p.exists()
    lines = p.read_text(encoding="utf-8").splitlines()
    assert len(lines) == 1
    record = json.loads(lines[0])
    assert record["external_id"] == "KAL-A"
    assert record["platform"] == "kalshi"
    assert record["bids"] == [[40, 100]]
    assert record["asks"] == [[50, 200]]
    assert record["time"] == "2026-05-01T12:00:00+00:00"
    assert "market_id" not in record  # renamed to external_id


def test_two_markets_in_one_batch_two_files(tmp_path):
    archive = OrderbookArchive(str(tmp_path))
    t = datetime(2026, 5, 1, 12, 0, 0, tzinfo=timezone.utc)
    written = archive.write_batch("kalshi", [
        _tick("MKT-A", t),
        _tick("MKT-B", t),
        _tick("MKT-A", t, bid=0.51),
    ])
    archive.close()

    assert written == 3
    a = (tmp_path / "kalshi" / "MKT-A" / "2026-05-01.jsonl").read_text(encoding="utf-8").splitlines()
    b = (tmp_path / "kalshi" / "MKT-B" / "2026-05-01.jsonl").read_text(encoding="utf-8").splitlines()
    assert len(a) == 2
    assert len(b) == 1


def test_date_rollover_opens_new_file(tmp_path):
    archive = OrderbookArchive(str(tmp_path))
    t1 = datetime(2026, 5, 1, 23, 59, 0, tzinfo=timezone.utc)
    t2 = datetime(2026, 5, 2, 0, 0, 1, tzinfo=timezone.utc)
    archive.write_batch("kalshi", [
        _tick("MKT-A", t1),
        _tick("MKT-A", t2),
    ])
    archive.close()

    f1 = (tmp_path / "kalshi" / "MKT-A" / "2026-05-01.jsonl").read_text(encoding="utf-8").splitlines()
    f2 = (tmp_path / "kalshi" / "MKT-A" / "2026-05-02.jsonl").read_text(encoding="utf-8").splitlines()
    assert len(f1) == 1
    assert len(f2) == 1


def test_lru_eviction_caps_open_handles(tmp_path):
    archive = OrderbookArchive(str(tmp_path), max_open_handles=2)
    t = datetime(2026, 5, 1, 12, 0, 0, tzinfo=timezone.utc)

    archive.write_batch("kalshi", [
        _tick("MKT-A", t),
        _tick("MKT-B", t),
        _tick("MKT-C", t),  # evicts MKT-A's handle
    ])
    assert len(archive._handles) == 2

    archive.write_batch("kalshi", [
        _tick("MKT-A", t, bid=0.6),  # re-opens MKT-A's file in append mode
    ])
    archive.close()

    a = (tmp_path / "kalshi" / "MKT-A" / "2026-05-01.jsonl").read_text(encoding="utf-8").splitlines()
    assert len(a) == 2  # both writes preserved across eviction
    second = json.loads(a[1])
    assert second["bid"] == 0.6


def test_malformed_tick_skipped_others_kept(tmp_path):
    archive = OrderbookArchive(str(tmp_path))
    t = datetime(2026, 5, 1, 12, 0, 0, tzinfo=timezone.utc)
    written = archive.write_batch("kalshi", [
        {"time": t, "bid": 0.5, "ask": 0.5},  # missing market_id
        {"market_id": "MKT-A", "bid": 0.5, "ask": 0.5},  # missing time
        _tick("MKT-OK", t),
    ])
    archive.close()

    assert written == 1
    p = tmp_path / "kalshi" / "MKT-OK" / "2026-05-01.jsonl"
    assert p.exists()
    assert len(p.read_text(encoding="utf-8").splitlines()) == 1


def test_path_components_sanitized(tmp_path):
    archive = OrderbookArchive(str(tmp_path))
    t = datetime(2026, 5, 1, 12, 0, 0, tzinfo=timezone.utc)
    archive.write_batch("kalshi", [_tick("../escape/attempt", t)])
    archive.close()

    # `..` collapses to `__`; slashes become `_`. End result has no
    # parent-dir traversal component.
    market_dir = tmp_path / "kalshi" / "___escape_attempt"
    assert market_dir.exists()
    # Confirm no escape outside root_dir occurred
    assert not (tmp_path.parent / "escape").exists()


async def test_stream_processor_writes_to_archive_when_provided(
    tmp_path, session_factory, sample_market
):
    archive = OrderbookArchive(str(tmp_path / "archive"))
    processor = StreamProcessor(
        "Kalshi", "kalshi", str(tmp_path / "ticks.jsonl"),
        archive=archive,
    )
    now = datetime.now(timezone.utc)
    processor.batch.append(_tick(
        sample_market.external_id, now,
        bid=0.41, ask=0.43,
        bids=[[41, 100]], asks=[[43, 100]],
    ))
    processor.batch[-1]["last_price"] = 0.42

    inserted = await processor._flush_once()
    archive.close()

    assert inserted == 1
    today = now.strftime("%Y-%m-%d")
    p = tmp_path / "archive" / "kalshi" / sample_market.external_id / f"{today}.jsonl"
    assert p.exists()
    rec = json.loads(p.read_text(encoding="utf-8").splitlines()[0])
    assert rec["external_id"] == sample_market.external_id
    assert rec["bids"] == [[41, 100]]


async def test_stream_processor_no_archive_when_none(
    tmp_path, session_factory, sample_market
):
    """When archive is not provided, no archive directory is touched."""
    processor = StreamProcessor("Kalshi", "kalshi", str(tmp_path / "ticks.jsonl"))
    processor.batch.append(_tick(
        sample_market.external_id, datetime.now(timezone.utc),
    ))
    inserted = await processor._flush_once()
    assert inserted == 1
    # Existing JSONL lake is written, but no orderbook_archive subtree exists.
    assert (tmp_path / "ticks.jsonl").exists()
    assert not any(p.is_dir() and p.name != tmp_path.name for p in tmp_path.iterdir() if p != tmp_path / "ticks.jsonl")
