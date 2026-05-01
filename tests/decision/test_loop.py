"""Decision-engine periodic loop — pumps Predictions into Orders."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from uuid import uuid4

import pytest
from sqlalchemy import select

from sigil.decision.loop import run_once
from sigil.models import (
    BankrollSnapshot,
    Market,
    MarketPrice,
    Order,
    Prediction,
)


async def _seed_market(session, *, platform="kalshi", external_id="KX-A", price=0.50):
    m = Market(
        id=uuid4(), platform=platform, external_id=external_id,
        title=f"{external_id} test market", taxonomy_l1="sports",
        market_type="binary", status="open",
    )
    session.add(m)
    session.add(MarketPrice(
        time=datetime.now(timezone.utc),
        market_id=m.id, bid=price - 0.01, ask=price + 0.01, last_price=price,
        source="test",
    ))
    # Seed a bankroll snapshot so drawdown logic doesn't halt us.
    session.add(BankrollSnapshot(
        time=datetime.now(timezone.utc), mode="paper",
        equity=5000.0, realized_pnl_total=0.0, unrealized_pnl_total=0.0,
        settled_trades_total=25, settled_trades_30d=10,
    ))
    await session.commit()
    return m


def _prediction(market_id, *, edge=0.20, predicted_prob=0.70, market_price=0.50):
    return Prediction(
        id=uuid4(),
        market_id=market_id,
        model_id="test_model", model_version="v1",
        predicted_prob=predicted_prob,
        confidence=0.9,
        market_price_at_prediction=market_price,
        edge=edge,
    )


async def test_creates_order_for_high_edge_kalshi(db_session):
    market = await _seed_market(db_session, platform="kalshi", external_id="KX-A", price=0.50)
    db_session.add(_prediction(market.id, edge=0.20, predicted_prob=0.70, market_price=0.50))
    await db_session.commit()

    n = await run_once(db_session, mode="paper")
    assert n == 1

    orders = (await db_session.execute(select(Order))).scalars().all()
    assert len(orders) == 1
    assert orders[0].market_id == market.id
    assert orders[0].mode == "paper"


async def test_skips_polymarket_predictions(db_session):
    market = await _seed_market(db_session, platform="polymarket", external_id="0xPOLY")
    db_session.add(_prediction(market.id, edge=0.20))
    await db_session.commit()

    n = await run_once(db_session, mode="paper")
    assert n == 0
    orders = (await db_session.execute(select(Order))).scalars().all()
    assert orders == []


async def test_skips_low_edge_below_threshold(db_session):
    """edge=0.05 is below MIN_EDGE_KALSHI=0.10 default, so the SQL filter
    (edge >= 0.10) drops it entirely."""
    market = await _seed_market(db_session, platform="kalshi")
    db_session.add(_prediction(market.id, edge=0.05))
    await db_session.commit()

    n = await run_once(db_session, mode="paper")
    assert n == 0


async def test_skips_predictions_already_with_order(db_session):
    market = await _seed_market(db_session, platform="kalshi")
    pred = _prediction(market.id, edge=0.20)
    db_session.add(pred)
    db_session.add(Order(
        id=uuid4(), client_order_id="existing", platform="kalshi",
        market_id=market.id, prediction_id=pred.id, mode="paper",
        side="buy", outcome="yes", order_type="limit",
        price=0.50, quantity=100, filled_quantity=100,
        status="filled",
    ))
    await db_session.commit()

    n = await run_once(db_session, mode="paper")
    assert n == 0
    orders = (await db_session.execute(select(Order))).scalars().all()
    assert len(orders) == 1  # the pre-existing one only


async def test_skips_when_no_recent_market_price(db_session):
    """Market exists but no MarketPrice rows -> can't price the trade -> skip."""
    m = Market(
        id=uuid4(), platform="kalshi", external_id="KX-NOPRICE",
        title="x", taxonomy_l1="sports", market_type="binary", status="open",
    )
    db_session.add(m)
    db_session.add(BankrollSnapshot(
        time=datetime.now(timezone.utc), mode="paper",
        equity=5000.0, realized_pnl_total=0.0, unrealized_pnl_total=0.0,
        settled_trades_total=25, settled_trades_30d=10,
    ))
    db_session.add(_prediction(m.id, edge=0.20))
    await db_session.commit()

    n = await run_once(db_session, mode="paper")
    assert n == 0


async def test_skips_old_predictions_outside_lookback(db_session):
    market = await _seed_market(db_session, platform="kalshi")
    pred = _prediction(market.id, edge=0.20)
    pred.created_at = datetime.now(timezone.utc) - timedelta(hours=4)
    db_session.add(pred)
    await db_session.commit()

    n = await run_once(db_session, mode="paper", lookback_seconds=3600)
    assert n == 0


async def test_evaluates_multiple_predictions_in_one_pass(db_session):
    """Two markets with two high-edge predictions -> two orders.

    Both edges need to be large enough that Kelly sizing returns a
    positive contract count at $5000 bankroll.
    """
    m1 = await _seed_market(db_session, platform="kalshi", external_id="KX-A", price=0.30)
    m2 = await _seed_market(db_session, platform="kalshi", external_id="KX-B", price=0.40)
    db_session.add(_prediction(m1.id, edge=0.40, predicted_prob=0.70, market_price=0.30))
    db_session.add(_prediction(m2.id, edge=0.30, predicted_prob=0.70, market_price=0.40))
    await db_session.commit()

    n = await run_once(db_session, mode="paper")
    assert n == 2

    orders = (await db_session.execute(select(Order))).scalars().all()
    assert len(orders) == 2
