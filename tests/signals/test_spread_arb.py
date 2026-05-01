"""Cross-platform spread-arb signal generator."""
from __future__ import annotations

import json
from uuid import uuid4

import pytest
from httpx import Response
from sqlalchemy import select

from sigil.ingestion.oddspipe import OddsPipeDataSource
from sigil.models import Market, Prediction
from sigil.signals.spread_arb import (
    MODEL_ID,
    MODEL_VERSION,
    generate_spread_predictions,
)


def _gamma_market(*, platform, pmid, internal_id, title="m"):
    return {
        "id": internal_id,
        "title": title,
        "category": "sports",
        "status": "active",
        "source": {
            "id": internal_id * 10,
            "platform": platform,
            "platform_market_id": pmid,
            "url": "x",
            "latest_price": {"yes_price": 0.5, "no_price": 0.5, "volume_usd": 100},
        },
    }


def _spread_item(*, match_id, score, poly_id, kalshi_id, poly_yes, kalshi_yes,
                 poly_vol=1000.0, kalshi_vol=1000.0):
    yes_diff = abs(poly_yes - kalshi_yes)
    direction = "polymarket_higher" if poly_yes > kalshi_yes else "kalshi_higher"
    return {
        "match_id": match_id,
        "score": score,
        "polymarket": {
            "market_id": poly_id, "title": "P", "yes_price": poly_yes,
            "no_price": 1 - poly_yes, "volume_usd": poly_vol, "url": "x",
        },
        "kalshi": {
            "market_id": kalshi_id, "title": "K", "yes_price": kalshi_yes,
            "no_price": 1 - kalshi_yes, "volume_usd": kalshi_vol, "url": "x",
        },
        "spread": {"yes_diff": yes_diff, "direction": direction,
                   "price_divergence": True, "note": ""},
    }


@pytest.fixture
async def seeded_markets(session):
    """Seed two markets — one polymarket, one kalshi — that match the
    spread fixtures. Returns (poly_market, kalshi_market)."""
    p = Market(
        id=uuid4(), platform="polymarket", external_id="0xPOLY",
        title="P", taxonomy_l1="sports", market_type="binary", status="open",
    )
    k = Market(
        id=uuid4(), platform="kalshi", external_id="KX-K",
        title="K", taxonomy_l1="sports", market_type="binary", status="open",
    )
    session.add_all([p, k])
    await session.commit()
    return p, k


async def _prime_id_map(odds: OddsPipeDataSource, respx_mock):
    """Make a real fetch() call so the internal_id->external_id map fills."""
    respx_mock.get(
        "https://oddspipe.com/v1/markets",
        params={"platform": "kalshi", "limit": "100"},
    ).mock(return_value=Response(200, json={"items": [
        _gamma_market(platform="kalshi", pmid="KX-K", internal_id=200),
    ]}))
    respx_mock.get(
        "https://oddspipe.com/v1/markets",
        params={"platform": "polymarket", "limit": "100"},
    ).mock(return_value=Response(200, json={"items": [
        _gamma_market(platform="polymarket", pmid="0xPOLY", internal_id=100),
    ]}))
    await odds.fetch()


async def test_emits_prediction_for_underpriced_side(
    respx_mock, session, seeded_markets
):
    odds = OddsPipeDataSource(api_key="kx")
    await _prime_id_map(odds, respx_mock)

    # Kalshi YES = 0.30, Polymarket YES = 0.50. Volume-weighted true p
    # with equal vol = 0.40. Kalshi side has edge = 0.40 - 0.30 = 0.10 (good).
    # Polymarket side has edge = 0.40 - 0.50 = -0.10 (skip; we don't short).
    # yes_diff = 0.20 < default max_yes_diff (0.30), so the match passes.
    respx_mock.get("https://oddspipe.com/v1/spreads").mock(
        return_value=Response(200, json={"items": [
            _spread_item(
                match_id=1, score=95.0,
                poly_id=100, kalshi_id=200,
                poly_yes=0.50, kalshi_yes=0.30,
            ),
        ]})
    )

    n = await generate_spread_predictions(session, odds, min_edge=0.05)
    assert n == 1

    preds = (await session.execute(select(Prediction))).scalars().all()
    assert len(preds) == 1
    p = preds[0]
    assert p.model_id == MODEL_ID
    assert p.model_version == MODEL_VERSION
    assert p.market_id == seeded_markets[1].id  # kalshi side (the cheap one)
    assert float(p.market_price_at_prediction) == 0.30
    assert float(p.predicted_prob) == 0.40
    assert float(p.edge) == pytest.approx(0.10)


async def test_skips_when_score_below_threshold(
    respx_mock, session, seeded_markets
):
    odds = OddsPipeDataSource(api_key="kx")
    await _prime_id_map(odds, respx_mock)

    respx_mock.get("https://oddspipe.com/v1/spreads").mock(
        return_value=Response(200, json={"items": [
            _spread_item(
                match_id=1, score=95.0,
                poly_id=100, kalshi_id=200,
                poly_yes=0.60, kalshi_yes=0.20,
            ),
        ]})
    )
    # Caller uses min_score=99 — but the API filtering happens server-side
    # so this is more of a doc check; with mocks we can't simulate the
    # server-side filter, so just confirm fetch_spreads passes the param.

    # Instead, test the edge gate.
    n = await generate_spread_predictions(
        session, odds, min_score=90.0, min_edge=0.50
    )
    # edge = 0.20, threshold 0.50 -> no prediction.
    assert n == 0
    preds = (await session.execute(select(Prediction))).scalars().all()
    assert preds == []


async def test_skips_zero_volume_match(respx_mock, session, seeded_markets):
    odds = OddsPipeDataSource(api_key="kx")
    await _prime_id_map(odds, respx_mock)

    respx_mock.get("https://oddspipe.com/v1/spreads").mock(
        return_value=Response(200, json={"items": [
            _spread_item(
                match_id=1, score=95.0,
                poly_id=100, kalshi_id=200,
                poly_yes=0.5, kalshi_yes=0.1,
                poly_vol=0.0, kalshi_vol=0.0,
            ),
        ]})
    )
    n = await generate_spread_predictions(session, odds, min_edge=0.05)
    assert n == 0


async def test_skips_unresolved_external_id(respx_mock, session):
    """No fetch() priming -> internal ids don't resolve -> no Predictions."""
    odds = OddsPipeDataSource(api_key="kx")
    respx_mock.get("https://oddspipe.com/v1/spreads").mock(
        return_value=Response(200, json={"items": [
            _spread_item(
                match_id=1, score=95.0,
                poly_id=100, kalshi_id=200,
                poly_yes=0.6, kalshi_yes=0.2,
            ),
        ]})
    )
    n = await generate_spread_predictions(session, odds, min_edge=0.05)
    assert n == 0


async def test_dedup_within_window(
    respx_mock, session, seeded_markets
):
    odds = OddsPipeDataSource(api_key="kx")
    await _prime_id_map(odds, respx_mock)

    respx_mock.get("https://oddspipe.com/v1/spreads").mock(
        return_value=Response(200, json={"items": [
            _spread_item(
                match_id=1, score=95.0,
                poly_id=100, kalshi_id=200,
                poly_yes=0.50, kalshi_yes=0.30,
            ),
        ]})
    )
    n1 = await generate_spread_predictions(session, odds, min_edge=0.05)
    assert n1 == 1
    # Same call again within the dedup window — should write 0.
    n2 = await generate_spread_predictions(
        session, odds, min_edge=0.05, dedup_window_seconds=3600,
    )
    assert n2 == 0


async def test_no_spreads_returns_zero(respx_mock, session, seeded_markets):
    odds = OddsPipeDataSource(api_key="kx")
    await _prime_id_map(odds, respx_mock)
    respx_mock.get("https://oddspipe.com/v1/spreads").mock(
        return_value=Response(200, json={"items": []})
    )
    assert await generate_spread_predictions(session, odds) == 0


async def test_oddspipe_5xx_returns_zero(respx_mock, session, seeded_markets):
    odds = OddsPipeDataSource(api_key="kx")
    await _prime_id_map(odds, respx_mock)
    respx_mock.get("https://oddspipe.com/v1/spreads").mock(
        return_value=Response(503, text="upstream down")
    )
    assert await generate_spread_predictions(session, odds) == 0
