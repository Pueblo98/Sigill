"""Polymarket adapter — gamma REST schema + WS book/price_change parsing."""
from __future__ import annotations

import json

import pandas as pd
import pytest

from sigil.ingestion.polymarket import PolymarketDataSource, _parse_json_array


def _gamma_market(
    *,
    cid="0xCID",
    yes_token="TOK_YES",
    no_token="TOK_NO",
    question="Will it happen?",
    category="politics",
    end_date="2026-06-01T00:00:00Z",
):
    return {
        "conditionId": cid,
        "question": question,
        "category": category,
        "active": True,
        "closed": False,
        "endDate": end_date,
        "clobTokenIds": json.dumps([yes_token, no_token]),
        "outcomes": json.dumps(["Yes", "No"]),
        "volume": "12345.6",
    }


def test_parse_json_array_handles_list_and_string():
    assert _parse_json_array(["a", "b"]) == ["a", "b"]
    assert _parse_json_array('["a", "b"]') == ["a", "b"]
    assert _parse_json_array("not-json") == []
    assert _parse_json_array(None) == []
    assert _parse_json_array("") == []


def test_normalize_camel_case_schema():
    src = PolymarketDataSource()
    df = src.normalize([_gamma_market(cid="0xABC", question="Foo?")])
    assert len(df) == 1
    row = df.iloc[0]
    assert row["external_id"] == "0xABC"
    assert row["platform"] == "polymarket"
    assert row["title"] == "Foo?"
    assert row["taxonomy_l1"] == "politics"
    assert row["resolution_date"] == "2026-06-01T00:00:00Z"


def test_normalize_skips_records_without_condition_id():
    src = PolymarketDataSource()
    df = src.normalize([
        {"conditionId": None, "question": "skip"},
        _gamma_market(cid="0xKEEP"),
    ])
    assert len(df) == 1
    assert df.iloc[0]["external_id"] == "0xKEEP"


def test_validate_empty_df():
    assert not PolymarketDataSource().validate(pd.DataFrame())


async def test_fetch_builds_yes_token_map(respx_mock):
    """fetch() should populate _yes_token_to_market keyed on the YES side
    only, mapping back to the conditionId."""
    import respx
    from httpx import Response

    respx_mock.get("https://gamma-api.polymarket.com/markets").mock(
        return_value=Response(200, json=[
            _gamma_market(cid="0xC1", yes_token="YES1", no_token="NO1"),
            _gamma_market(cid="0xC2", yes_token="YES2", no_token="NO2"),
        ])
    )
    src = PolymarketDataSource()
    rows = await src.fetch()
    assert len(rows) == 2
    assert src._yes_token_to_market == {"YES1": "0xC1", "YES2": "0xC2"}
    assert "NO1" not in src._yes_token_to_market
    assert sorted(src.yes_token_ids) == ["YES1", "YES2"]


async def test_fetch_falls_back_to_position_zero_when_outcomes_missing(respx_mock):
    """If outcomes is missing/non-standard, position 0 of clobTokenIds is YES."""
    from httpx import Response
    respx_mock.get("https://gamma-api.polymarket.com/markets").mock(
        return_value=Response(200, json=[{
            "conditionId": "0xCQ",
            "question": "edge case",
            "active": True,
            "closed": False,
            "clobTokenIds": json.dumps(["FIRST", "SECOND"]),
            # outcomes intentionally missing
        }])
    )
    src = PolymarketDataSource()
    await src.fetch()
    assert src._yes_token_to_market == {"FIRST": "0xCQ"}


async def _drain(it):
    out = []
    async for x in it:
        out.append(x)
    return out


async def test_yield_book_emits_yes_side_only():
    src = PolymarketDataSource()
    src._yes_token_to_market = {"YES_TOKEN": "0xCID"}

    yes_event = {
        "event_type": "book",
        "asset_id": "YES_TOKEN",
        "market": "0xCID",
        "bids": [{"price": "0.40", "size": "100"}, {"price": "0.39", "size": "50"}],
        "asks": [{"price": "0.43", "size": "200"}, {"price": "0.44", "size": "75"}],
        "last_trade_price": "0.42",
    }
    no_event = dict(yes_event, asset_id="NO_TOKEN")

    yes_ticks = await _drain(src._yield_book(yes_event))
    no_ticks = await _drain(src._yield_book(no_event))

    assert len(yes_ticks) == 1
    assert len(no_ticks) == 0
    t = yes_ticks[0]
    assert t["market_id"] == "0xCID"
    assert t["bid"] == 0.40         # max of bids
    assert t["ask"] == 0.43         # min of asks
    assert t["last_price"] == 0.42  # from last_trade_price
    assert t["bids"] == yes_event["bids"]
    assert t["asks"] == yes_event["asks"]


async def test_yield_price_changes_uses_included_best_bid_ask():
    src = PolymarketDataSource()
    src._yes_token_to_market = {"YES": "0xCID"}
    event = {
        "event_type": "price_change",
        "market": "0xCID",
        "price_changes": [
            {"asset_id": "YES", "price": "0.41", "size": "10",
             "side": "BUY", "best_bid": "0.41", "best_ask": "0.43"},
            {"asset_id": "NO_TOKEN", "price": "0.59", "size": "10",
             "side": "SELL", "best_bid": "0.59", "best_ask": "0.61"},
        ],
    }
    ticks = await _drain(src._yield_price_changes(event))
    assert len(ticks) == 1
    t = ticks[0]
    assert t["market_id"] == "0xCID"
    assert t["bid"] == 0.41
    assert t["ask"] == 0.43


async def test_yield_book_handles_empty_ladder():
    src = PolymarketDataSource()
    src._yes_token_to_market = {"YES": "0xC"}
    event = {
        "event_type": "book",
        "asset_id": "YES",
        "market": "0xC",
        "bids": [],
        "asks": [],
        "last_trade_price": None,
    }
    ticks = await _drain(src._yield_book(event))
    assert len(ticks) == 1
    t = ticks[0]
    assert t["bid"] is None
    assert t["ask"] is None
    assert t["last_price"] is None
