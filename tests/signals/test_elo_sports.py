"""Elo NBA signal — v0 scaffolding."""
from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

import pytest
from sqlalchemy import select

from sigil.models import Market, MarketPrice, Prediction
from sigil.signals.elo_sports import (
    MODEL_ID,
    _elo_win_probability,
    _parse_kalshi_nba,
    generate_elo_predictions,
)


def test_parse_kalshi_nba_three_three():
    p = _parse_kalshi_nba("KXNBAGAME-26MAY01CLETOR-CLE")
    assert p is not None
    assert p.away == "CLE"
    assert p.home == "TOR"
    assert p.bet_on == "CLE"


def test_parse_kalshi_nba_normalizes_aliases():
    # NO -> NOP via alias map
    p = _parse_kalshi_nba("KXNBAGAME-26MAY01NOMIA-NOP")
    assert p is not None
    assert p.away == "NOP"


def test_parse_kalshi_nba_returns_none_on_unknown_team():
    p = _parse_kalshi_nba("KXNBAGAME-26MAY01XYZABC-XYZ")
    assert p is None


def test_parse_kalshi_nba_returns_none_on_non_nba_ticker():
    assert _parse_kalshi_nba("KXMLBGAME-26MAY01CHCAZ-CHC") is None
    assert _parse_kalshi_nba("KXNBASPREAD-26MAY01CLETOR-CLE3") is None


def test_elo_win_probability_home_advantage():
    p_home = _elo_win_probability(home="BOS", away="DET")
    assert 0.7 < p_home < 0.95  # Boston heavy favorite + home court
    p_away = _elo_win_probability(home="DET", away="BOS")
    assert 1 - p_away > 0.5  # away team (BOS) still likely wins
    # Symmetry-ish check: home court favors the home team
    p_h_then_a = _elo_win_probability(home="BOS", away="MIN")
    p_a_then_h = _elo_win_probability(home="MIN", away="BOS")
    assert p_h_then_a + p_a_then_h > 1.0  # both teams favored at home


async def _seed_kalshi_market_with_price(session, ticker, price):
    m = Market(
        id=uuid4(), platform="kalshi", external_id=ticker,
        title=ticker, taxonomy_l1="sports", market_type="binary", status="open",
    )
    session.add(m)
    session.add(MarketPrice(
        time=datetime.now(timezone.utc),
        market_id=m.id, last_price=price, source="test",
    ))
    await session.commit()
    return m


async def test_emits_prediction_for_undervalued_favorite(session):
    # BOS vs DET: BOS heavy favorite; if market prices BOS at 0.50 we
    # should see a strong positive edge.
    m = await _seed_kalshi_market_with_price(
        session, "KXNBAGAME-26MAY01DETBOS-BOS", price=0.50,
    )
    n = await generate_elo_predictions(session, min_edge=0.05)
    assert n == 1
    pred = (await session.execute(
        select(Prediction).where(Prediction.market_id == m.id)
    )).scalar_one()
    assert pred.model_id == MODEL_ID
    assert float(pred.predicted_prob) > 0.70
    assert float(pred.edge) > 0.20


async def test_skips_market_priced_above_elo(session):
    # BOS heavy favorite; market already prices them at 0.95 so no edge.
    await _seed_kalshi_market_with_price(
        session, "KXNBAGAME-26MAY01DETBOS-BOS", price=0.95,
    )
    n = await generate_elo_predictions(session, min_edge=0.05)
    assert n == 0


async def test_skips_unparseable_ticker(session):
    # Multi-leg combo ticker — won't match the single-game regex.
    await _seed_kalshi_market_with_price(
        session, "KXMVECROSSCATEGORY-S2026X-Y", price=0.40,
    )
    n = await generate_elo_predictions(session, min_edge=0.05)
    assert n == 0


async def test_dedup_within_window(session):
    await _seed_kalshi_market_with_price(
        session, "KXNBAGAME-26MAY01DETBOS-BOS", price=0.40,
    )
    n1 = await generate_elo_predictions(session, min_edge=0.05)
    assert n1 == 1
    n2 = await generate_elo_predictions(
        session, min_edge=0.05, dedup_window_seconds=3600,
    )
    assert n2 == 0
