"""Runner FK-type bug regression + source health writer."""
from __future__ import annotations

from datetime import datetime, timezone

import pytest
from sqlalchemy import select

from sigil.config import config
from sigil.ingestion.runner import (
    MarketIdResolver,
    SourceHealthWriter,
    StreamProcessor,
    is_source_emergency,
)
from sigil.models import MarketPrice, SourceHealth


@pytest.mark.critical
async def test_resolver_maps_external_id_to_uuid(session, sample_market):
    resolver = MarketIdResolver()
    market_id = await resolver.resolve(session, "kalshi", sample_market.external_id)
    assert market_id == sample_market.id
    # cached:
    assert resolver.cache_size() == 1
    # second call returns cached value without DB query
    again = await resolver.resolve(session, "kalshi", sample_market.external_id)
    assert again == sample_market.id


@pytest.mark.critical
async def test_resolver_returns_none_for_unknown_market(session):
    resolver = MarketIdResolver()
    assert await resolver.resolve(session, "kalshi", "MISSING-EXT") is None
    assert resolver.cache_size() == 0


@pytest.mark.critical
async def test_stream_processor_persists_with_correct_uuid(tmp_path, session_factory, sample_market):
    cache_file = str(tmp_path / "kalshi.jsonl")
    processor = StreamProcessor("Kalshi", "kalshi", cache_file)
    processor.batch.append({
        "market_id": sample_market.external_id,  # external_id (string) on the wire
        "platform": "kalshi",
        "bid": 0.41, "ask": 0.43, "last_price": 0.42,
        "time": datetime.now(timezone.utc),
        "source": "exchange_ws",
    })
    inserted = await processor._flush_once()
    assert inserted == 1
    assert processor.dropped_unknown_market == 0

    async with session_factory() as session:
        rows = (await session.execute(select(MarketPrice))).scalars().all()
        assert len(rows) == 1
        assert rows[0].market_id == sample_market.id
        assert float(rows[0].bid) == 0.41


@pytest.mark.critical
async def test_stream_processor_drops_unknown_market_id(tmp_path, session_factory):
    cache_file = str(tmp_path / "kalshi.jsonl")
    processor = StreamProcessor("Kalshi", "kalshi", cache_file)
    processor.batch.append({
        "market_id": "GHOST-EXT",
        "platform": "kalshi",
        "bid": 0.5, "ask": 0.5, "last_price": 0.5,
        "time": datetime.now(timezone.utc),
        "source": "exchange_ws",
    })
    inserted = await processor._flush_once()
    assert inserted == 0
    assert processor.dropped_unknown_market == 1


async def test_source_health_emits_warning_then_critical(session_factory):
    writer = SourceHealthWriter(warning_threshold=2, critical_threshold=4)
    async with session_factory() as s:
        for i in range(3):
            state = await writer.record("kalshi", success=False, session=s, error_message="boom")
        await s.commit()
    assert state.consecutive_failures == 3
    assert is_source_emergency("kalshi") is False  # below critical

    async with session_factory() as s:
        state = await writer.record("kalshi", success=False, session=s, error_message="boom")
        await s.commit()
    assert state.consecutive_failures == 4
    assert is_source_emergency("kalshi") is True


async def test_source_health_resets_on_success(session_factory):
    writer = SourceHealthWriter(warning_threshold=2, critical_threshold=3)
    async with session_factory() as s:
        await writer.record("kalshi", success=False, session=s)
        await writer.record("kalshi", success=False, session=s)
        await writer.record("kalshi", success=False, session=s)
        await s.commit()
    assert is_source_emergency("kalshi") is True

    async with session_factory() as s:
        state = await writer.record("kalshi", success=True, session=s, records_fetched=10)
        await s.commit()
    assert state.consecutive_failures == 0
    assert is_source_emergency("kalshi") is False

    async with session_factory() as s:
        rows = (await s.execute(select(SourceHealth).where(SourceHealth.source_name == "kalshi"))).scalars().all()
        assert any(r.status == "ok" for r in rows)
        assert any(r.status == "error" for r in rows)
