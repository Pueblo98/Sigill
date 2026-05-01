"""Replay reader for the orderbook archive (TODO-9)."""
from __future__ import annotations

import json
from datetime import date, datetime, timezone
from pathlib import Path
from uuid import UUID, uuid4

import pytest

from sigil.backtesting.engine import PriceTick
from sigil.backtesting.replay import iter_archive_ticks, load_market_id_map
from sigil.ingestion.orderbook_archive import OrderbookArchive


def _write_line(p: Path, **fields) -> None:
    p.parent.mkdir(parents=True, exist_ok=True)
    with p.open("a", encoding="utf-8") as f:
        f.write(json.dumps(fields) + "\n")


def test_yields_single_tick(tmp_path):
    market_uuid = uuid4()
    p = tmp_path / "kalshi" / "MKT-A" / "2026-05-01.jsonl"
    _write_line(
        p,
        time="2026-05-01T12:00:00+00:00",
        platform="kalshi",
        external_id="MKT-A",
        bid=0.4, ask=0.5, last_price=0.45, volume_24h=1234.0,
        bids=[[40, 100]], asks=[[50, 200]], source="exchange_ws",
    )

    ticks = list(iter_archive_ticks(
        tmp_path,
        market_id_map={("kalshi", "MKT-A"): market_uuid},
        start_date=date(2026, 5, 1),
        end_date=date(2026, 5, 1),
    ))
    assert len(ticks) == 1
    t = ticks[0]
    assert isinstance(t, PriceTick)
    assert t.market_id == market_uuid
    assert t.bid == 0.4
    assert t.ask == 0.5
    assert t.trade_price == 0.45  # last_price -> trade_price
    assert t.volume_24h == 1234.0
    assert t.timestamp == datetime(2026, 5, 1, 12, 0, 0, tzinfo=timezone.utc)


def test_chronological_across_days(tmp_path):
    market_uuid = uuid4()
    # Day 1 has a later tick first (mimics an out-of-order write within a day).
    p1 = tmp_path / "kalshi" / "MKT-A" / "2026-05-01.jsonl"
    _write_line(p1, time="2026-05-01T18:00:00+00:00",
                bid=0.5, ask=0.5, last_price=0.5, external_id="MKT-A")
    _write_line(p1, time="2026-05-01T06:00:00+00:00",
                bid=0.4, ask=0.4, last_price=0.4, external_id="MKT-A")
    p2 = tmp_path / "kalshi" / "MKT-A" / "2026-05-02.jsonl"
    _write_line(p2, time="2026-05-02T01:00:00+00:00",
                bid=0.6, ask=0.6, last_price=0.6, external_id="MKT-A")

    ticks = list(iter_archive_ticks(
        tmp_path,
        market_id_map={("kalshi", "MKT-A"): market_uuid},
        start_date=date(2026, 5, 1),
        end_date=date(2026, 5, 2),
    ))
    assert [t.trade_price for t in ticks] == [0.4, 0.5, 0.6]


def test_multi_market_interleaved(tmp_path):
    a, b = uuid4(), uuid4()
    pa = tmp_path / "kalshi" / "MKT-A" / "2026-05-01.jsonl"
    pb = tmp_path / "kalshi" / "MKT-B" / "2026-05-01.jsonl"
    _write_line(pa, time="2026-05-01T10:00:00+00:00", last_price=0.40, external_id="MKT-A")
    _write_line(pa, time="2026-05-01T14:00:00+00:00", last_price=0.42, external_id="MKT-A")
    _write_line(pb, time="2026-05-01T11:00:00+00:00", last_price=0.60, external_id="MKT-B")
    _write_line(pb, time="2026-05-01T13:00:00+00:00", last_price=0.65, external_id="MKT-B")

    ticks = list(iter_archive_ticks(
        tmp_path,
        market_id_map={("kalshi", "MKT-A"): a, ("kalshi", "MKT-B"): b},
        start_date=date(2026, 5, 1),
        end_date=date(2026, 5, 1),
    ))
    assert [t.trade_price for t in ticks] == [0.40, 0.60, 0.65, 0.42]
    assert [t.market_id for t in ticks] == [a, b, b, a]


def test_external_ids_whitelist(tmp_path):
    a, b = uuid4(), uuid4()
    pa = tmp_path / "kalshi" / "MKT-A" / "2026-05-01.jsonl"
    pb = tmp_path / "kalshi" / "MKT-B" / "2026-05-01.jsonl"
    _write_line(pa, time="2026-05-01T10:00:00+00:00", last_price=0.4, external_id="MKT-A")
    _write_line(pb, time="2026-05-01T11:00:00+00:00", last_price=0.6, external_id="MKT-B")

    ticks = list(iter_archive_ticks(
        tmp_path,
        market_id_map={("kalshi", "MKT-A"): a, ("kalshi", "MKT-B"): b},
        start_date=date(2026, 5, 1),
        end_date=date(2026, 5, 1),
        external_ids=["MKT-A"],
    ))
    assert len(ticks) == 1
    assert ticks[0].market_id == a


def test_unmapped_market_skipped(tmp_path, caplog):
    p = tmp_path / "kalshi" / "MKT-A" / "2026-05-01.jsonl"
    _write_line(p, time="2026-05-01T10:00:00+00:00", last_price=0.4, external_id="MKT-A")

    with caplog.at_level("WARNING"):
        ticks = list(iter_archive_ticks(
            tmp_path,
            market_id_map={},  # no resolution for MKT-A
            start_date=date(2026, 5, 1),
            end_date=date(2026, 5, 1),
        ))
    assert ticks == []
    assert any("MKT-A" in rec.message for rec in caplog.records)


def test_malformed_json_line_skipped(tmp_path, caplog):
    market_uuid = uuid4()
    p = tmp_path / "kalshi" / "MKT-A" / "2026-05-01.jsonl"
    p.parent.mkdir(parents=True, exist_ok=True)
    with p.open("w", encoding="utf-8") as f:
        f.write('{"time": "2026-05-01T10:00:00+00:00", "last_price": 0.4}\n')
        f.write("{not valid json\n")
        f.write('{"time": "2026-05-01T11:00:00+00:00", "last_price": 0.5}\n')

    with caplog.at_level("WARNING"):
        ticks = list(iter_archive_ticks(
            tmp_path,
            market_id_map={("kalshi", "MKT-A"): market_uuid},
            start_date=date(2026, 5, 1),
            end_date=date(2026, 5, 1),
        ))
    assert [t.trade_price for t in ticks] == [0.4, 0.5]
    assert any("malformed JSON" in rec.message for rec in caplog.records)


def test_missing_archive_root_yields_nothing(tmp_path, caplog):
    with caplog.at_level("WARNING"):
        ticks = list(iter_archive_ticks(
            tmp_path / "does-not-exist",
            market_id_map={},
            start_date=date(2026, 5, 1),
            end_date=date(2026, 5, 1),
        ))
    assert ticks == []
    assert any("missing" in rec.message for rec in caplog.records)


def test_round_trip_writer_to_reader(tmp_path):
    """End-to-end: OrderbookArchive writes, iter_archive_ticks reads back."""
    market_uuid = uuid4()
    archive = OrderbookArchive(str(tmp_path))
    t1 = datetime(2026, 5, 1, 9, 0, 0, tzinfo=timezone.utc)
    t2 = datetime(2026, 5, 1, 9, 0, 1, tzinfo=timezone.utc)
    archive.write_batch("kalshi", [
        {"market_id": "MKT-A", "platform": "kalshi", "time": t1,
         "bid": 0.40, "ask": 0.42, "last_price": 0.41,
         "volume_24h": 1000.0, "bids": [[40, 100]], "asks": [[42, 200]],
         "source": "exchange_ws"},
        {"market_id": "MKT-A", "platform": "kalshi", "time": t2,
         "bid": 0.41, "ask": 0.43, "last_price": 0.42,
         "volume_24h": 1100.0, "bids": [[41, 100]], "asks": [[43, 200]],
         "source": "exchange_ws"},
    ])
    archive.close()

    ticks = list(iter_archive_ticks(
        tmp_path,
        market_id_map={("kalshi", "MKT-A"): market_uuid},
        start_date=date(2026, 5, 1),
        end_date=date(2026, 5, 1),
    ))
    assert len(ticks) == 2
    assert ticks[0].timestamp == t1
    assert ticks[0].trade_price == 0.41
    assert ticks[0].bid == 0.40
    assert ticks[1].timestamp == t2
    assert ticks[1].trade_price == 0.42


async def test_load_market_id_map_from_db(session, sample_market):
    mapping = await load_market_id_map(session, platform="kalshi")
    assert (("kalshi", sample_market.external_id)) in mapping
    assert mapping[("kalshi", sample_market.external_id)] == sample_market.id
    assert all(plat == "kalshi" for (plat, _) in mapping)
