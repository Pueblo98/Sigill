"""Kalshi REST shape parsing for the new api.elections.kalshi.com schema."""
from __future__ import annotations

import pandas as pd

from sigil.ingestion.kalshi import KalshiDataSource


def _kalshi_record(**overrides):
    """Mimics one record in body.markets[] from the new Kalshi schema."""
    base = {
        "ticker": "KXEXAMPLE-26MAY01-X",
        "event_ticker": "KXEXAMPLE",
        "title": "Example market title",
        "yes_sub_title": "yes ABC",
        "no_sub_title": "no ABC",
        "status": "active",
        "expiration_time": "2026-05-15T23:30:00Z",
        "market_type": "binary",
        "yes_bid_dollars": "0.4200",
        "yes_ask_dollars": "0.4300",
        "last_price_dollars": "0.4200",
    }
    base.update(overrides)
    return base


def test_normalize_active_status_maps_to_open():
    src = KalshiDataSource()
    df = src.normalize([_kalshi_record(status="active")])
    assert len(df) == 1
    assert df.iloc[0]["status"] == "open"
    assert df.iloc[0]["external_id"] == "KXEXAMPLE-26MAY01-X"
    assert df.iloc[0]["platform"] == "kalshi"


def test_normalize_skips_records_without_ticker():
    src = KalshiDataSource()
    df = src.normalize([
        _kalshi_record(ticker=None),
        _kalshi_record(ticker="KX-OK"),
    ])
    assert len(df) == 1
    assert df.iloc[0]["external_id"] == "KX-OK"


def test_normalize_falls_back_to_yes_subtitle_for_title():
    src = KalshiDataSource()
    df = src.normalize([_kalshi_record(title=None, yes_sub_title="fallback title")])
    assert df.iloc[0]["title"] == "fallback title"


def test_normalize_taxonomy_default_general():
    """category has moved off /markets onto /events; we default to 'general'."""
    src = KalshiDataSource()
    df = src.normalize([_kalshi_record()])
    assert df.iloc[0]["taxonomy_l1"] == "general"


def test_normalize_resolution_date_field_priority():
    src = KalshiDataSource()
    df = src.normalize([_kalshi_record(
        expiration_time="2026-06-01T00:00:00Z",
        close_time="2026-05-15T00:00:00Z",
    )])
    assert df.iloc[0]["resolution_date"] == "2026-06-01T00:00:00Z"


def test_validate_empty_df():
    src = KalshiDataSource()
    assert not src.validate(pd.DataFrame())


def test_validate_full_df():
    src = KalshiDataSource()
    df = src.normalize([_kalshi_record()])
    assert src.validate(df)


def test_normalize_finalized_status_passes_through():
    """Non-active statuses pass through (e.g. 'finalized') so the runner
    doesn't drop rows we want to update."""
    src = KalshiDataSource()
    df = src.normalize([_kalshi_record(status="finalized")])
    assert df.iloc[0]["status"] == "finalized"
