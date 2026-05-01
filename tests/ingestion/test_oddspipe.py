"""OddsPipe REST poller — schema parsing + tick emission."""
from __future__ import annotations

import pandas as pd
import pytest
from httpx import Response

from sigil.ingestion.oddspipe import OddsPipeAuthError, OddsPipeDataSource


def _market(
    *,
    platform="polymarket",
    pmid="0xCID-or-KX-ticker",
    title="Will it rain tomorrow?",
    category="weather",
    status="active",
    yes=0.42,
    no=0.58,
    vol=12345.6,
):
    return {
        "id": 1,
        "title": title,
        "category": category,
        "status": status,
        "source": {
            "platform": platform,
            "platform_market_id": pmid,
            "url": f"https://example.com/{pmid}",
            "latest_price": {
                "yes_price": yes,
                "no_price": no,
                "volume_usd": vol,
                "snapshot_at": "2026-05-01T17:00:00+00:00",
            },
        },
    }


def test_normalize_active_status_maps_to_open():
    src = OddsPipeDataSource(api_key="kx")
    df = src.normalize([_market(platform="kalshi", pmid="KX-A", status="active")])
    assert len(df) == 1
    row = df.iloc[0]
    assert row["external_id"] == "KX-A"
    assert row["platform"] == "kalshi"
    assert row["status"] == "open"
    assert row["taxonomy_l1"] == "weather"


def test_normalize_skips_records_missing_platform_market_id():
    src = OddsPipeDataSource(api_key="kx")
    bad = _market(pmid=None)
    df = src.normalize([bad, _market(pmid="OK")])
    assert df["external_id"].tolist() == ["OK"]


def test_normalize_taxonomy_default_general_when_category_missing():
    src = OddsPipeDataSource(api_key="kx")
    m = _market(category=None)
    df = src.normalize([m])
    assert df.iloc[0]["taxonomy_l1"] == "general"


def test_validate():
    src = OddsPipeDataSource(api_key="kx")
    assert not src.validate(pd.DataFrame())
    assert src.validate(src.normalize([_market()]))


def test_emit_tick_yes_only_with_volume():
    tick = OddsPipeDataSource._emit_tick(
        _market(platform="kalshi", pmid="KX-A", yes=0.40, no=0.60, vol=999.5)
    )
    assert tick is not None
    assert tick["market_id"] == "KX-A"
    assert tick["platform"] == "kalshi"
    assert tick["bid"] == 0.40
    assert tick["ask"] == 0.40
    assert tick["last_price"] == 0.40
    assert tick["volume_24h"] == 999.5
    assert tick["source"] == "oddspipe"


def test_emit_tick_returns_none_for_missing_yes_price():
    bad = _market(yes=None)
    assert OddsPipeDataSource._emit_tick(bad) is None


def test_emit_tick_returns_none_for_missing_platform_market_id():
    bad = _market(pmid=None)
    assert OddsPipeDataSource._emit_tick(bad) is None


async def test_no_api_key_raises_on_fetch():
    src = OddsPipeDataSource(api_key=None)
    with pytest.raises(OddsPipeAuthError):
        await src.fetch()


async def test_fetch_merges_both_platforms(respx_mock):
    respx_mock.get(
        "https://oddspipe.com/v1/markets",
        params={"platform": "kalshi", "limit": "10"},
    ).mock(return_value=Response(200, json={
        "total": 1, "limit": 10, "offset": 0,
        "items": [_market(platform="kalshi", pmid="KX-A")],
    }))
    respx_mock.get(
        "https://oddspipe.com/v1/markets",
        params={"platform": "polymarket", "limit": "10"},
    ).mock(return_value=Response(200, json={
        "total": 1, "limit": 10, "offset": 0,
        "items": [_market(platform="polymarket", pmid="0xC1")],
    }))

    src = OddsPipeDataSource(api_key="kx", markets_per_platform=10)
    items = await src.fetch()
    assert len(items) == 2
    platforms = {it["source"]["platform"] for it in items}
    assert platforms == {"kalshi", "polymarket"}


async def test_fetch_continues_when_one_platform_5xx(respx_mock, caplog):
    respx_mock.get(
        "https://oddspipe.com/v1/markets",
        params={"platform": "kalshi", "limit": "10"},
    ).mock(return_value=Response(500, text="boom"))
    respx_mock.get(
        "https://oddspipe.com/v1/markets",
        params={"platform": "polymarket", "limit": "10"},
    ).mock(return_value=Response(200, json={
        "total": 0, "limit": 10, "offset": 0,
        "items": [_market(platform="polymarket", pmid="0xOK")],
    }))

    src = OddsPipeDataSource(api_key="kx", markets_per_platform=10)
    with caplog.at_level("WARNING"):
        items = await src.fetch()
    # Only the Polymarket page survived; Kalshi 500 was logged + skipped.
    assert len(items) == 1
    assert items[0]["source"]["platform"] == "polymarket"
    assert any("kalshi" in rec.message.lower() for rec in caplog.records)


async def test_stream_prices_yields_one_cycle(respx_mock):
    respx_mock.get(
        "https://oddspipe.com/v1/markets",
        params={"platform": "kalshi", "limit": "5"},
    ).mock(return_value=Response(200, json={
        "items": [_market(platform="kalshi", pmid="KX-A", yes=0.4)],
    }))
    respx_mock.get(
        "https://oddspipe.com/v1/markets",
        params={"platform": "polymarket", "limit": "5"},
    ).mock(return_value=Response(200, json={
        "items": [_market(platform="polymarket", pmid="0xC1", yes=0.55)],
    }))

    src = OddsPipeDataSource(api_key="kx", markets_per_platform=5)
    # poll_interval=3600 means after the first cycle we'd block forever;
    # we just consume the cycle and stop.
    ticks = []
    gen = src.stream_prices([], poll_interval=3600)
    # collect the first batch (one tick per market) using anext-driven loop
    async for tick in gen:
        ticks.append(tick)
        if len(ticks) == 2:
            break
    platforms = {t["platform"] for t in ticks}
    assert platforms == {"kalshi", "polymarket"}
    assert all(t["source"] == "oddspipe" for t in ticks)
    assert {t["bid"] for t in ticks} == {0.4, 0.55}
