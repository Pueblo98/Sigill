"""Pre-trade risk — every check fails closed independently."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from uuid import uuid4

import pytest

from sigil.config import config
from sigil.execution.risk import TradeIntent, evaluate
from sigil.models import BankrollSnapshot, Market, Position


def _intent(market_id, **over):
    base = dict(
        platform="kalshi",
        market_id=market_id,
        outcome="yes",
        side="buy",
        price=0.50,
        quantity=10,
        order_type="limit",
        mode="paper",
        category="sports",
        model_id="m_test",
        model_healthy=True,
        bankroll=5000.0,
    )
    base.update(over)
    return TradeIntent(**base)


@pytest.mark.critical
async def test_all_checks_pass_with_clean_state(session, sample_market, sample_bankroll):
    result = await evaluate(session, _intent(sample_market.id))
    assert result.passed, result.reason


@pytest.mark.critical
async def test_balance_fails_when_intent_bankroll_too_low(session, sample_market, sample_bankroll):
    intent = _intent(sample_market.id, price=10.0, quantity=1000, bankroll=100.0)
    result = await evaluate(session, intent)
    assert not result.passed
    assert any(f.check == "balance" for f in result.failures)


@pytest.mark.critical
async def test_balance_fails_closed_with_no_snapshot_and_no_intent_bankroll(session, sample_market):
    intent = _intent(sample_market.id, bankroll=None)
    result = await evaluate(session, intent)
    assert not result.passed
    assert any(f.check == "balance" for f in result.failures)


@pytest.mark.critical
async def test_per_market_limit_blocks_overshoot(session, sample_market, sample_bankroll):
    cap = 5000.0 * config.MAX_POSITION_PCT / 100.0  # 250
    session.add(Position(
        id=uuid4(),
        platform="kalshi",
        market_id=sample_market.id,
        mode="paper",
        outcome="yes",
        quantity=int(cap / 0.5),  # exactly at cap
        avg_entry_price=0.5,
        status="open",
    ))
    await session.commit()

    intent = _intent(sample_market.id, price=0.5, quantity=10)
    result = await evaluate(session, intent)
    assert not result.passed
    assert any(f.check == "per_market" for f in result.failures)


@pytest.mark.critical
async def test_per_category_blocks(session, sample_market, sample_bankroll):
    other = Market(
        id=uuid4(), platform="kalshi", external_id="OTHER",
        title="other sports market", taxonomy_l1="sports",
        market_type="binary", status="open",
    )
    session.add(other)
    cap = 5000.0 * config.MAX_CATEGORY_EXPOSURE_PCT / 100.0  # 1250
    session.add(Position(
        id=uuid4(), platform="kalshi", market_id=other.id,
        mode="paper", outcome="yes",
        quantity=int(cap / 0.5),
        avg_entry_price=0.5,
        status="open",
    ))
    await session.commit()

    intent = _intent(sample_market.id, price=0.5, quantity=20)
    result = await evaluate(session, intent)
    assert not result.passed
    assert any(f.check == "per_category" for f in result.failures)


@pytest.mark.critical
async def test_per_platform_blocks(session, sample_market, sample_bankroll):
    cap = 5000.0 * config.MAX_PLATFORM_EXPOSURE_PCT / 100.0  # 2500
    other = Market(
        id=uuid4(), platform="kalshi", external_id="OTHER2",
        title="x", taxonomy_l1="economics",
        market_type="binary", status="open",
    )
    session.add(other)
    session.add(Position(
        id=uuid4(), platform="kalshi", market_id=other.id,
        mode="paper", outcome="yes",
        quantity=int(cap / 0.5),
        avg_entry_price=0.5,
        status="open",
    ))
    await session.commit()

    intent = _intent(sample_market.id, price=0.5, quantity=20)
    result = await evaluate(session, intent)
    assert not result.passed
    assert any(f.check == "per_platform" for f in result.failures)


@pytest.mark.critical
async def test_drawdown_blocks_when_gates_met(session, sample_market):
    now = datetime.now(timezone.utc)
    # Peak snapshot
    session.add(BankrollSnapshot(
        time=now - timedelta(days=10),
        mode="paper",
        equity=10_000.0,
        realized_pnl_total=0.0,
        unrealized_pnl_total=0.0,
        settled_trades_total=25,
        settled_trades_30d=10,
    ))
    # Recent snapshot deep underwater
    session.add(BankrollSnapshot(
        time=now,
        mode="paper",
        equity=8_000.0,  # 20% drawdown
        realized_pnl_total=-2_000.0,
        unrealized_pnl_total=0.0,
        settled_trades_total=30,
        settled_trades_30d=10,
    ))
    await session.commit()

    intent = _intent(sample_market.id, bankroll=8_000.0)
    result = await evaluate(session, intent)
    assert not result.passed
    assert any(f.check == "drawdown" for f in result.failures)


@pytest.mark.critical
async def test_drawdown_does_not_trip_below_min_settled(session, sample_market):
    now = datetime.now(timezone.utc)
    session.add(BankrollSnapshot(
        time=now - timedelta(days=10),
        mode="paper",
        equity=10_000.0,
        realized_pnl_total=0.0, unrealized_pnl_total=0.0,
        settled_trades_total=2, settled_trades_30d=1,  # below gate
    ))
    session.add(BankrollSnapshot(
        time=now,
        mode="paper",
        equity=7_000.0,
        realized_pnl_total=-3_000.0, unrealized_pnl_total=0.0,
        settled_trades_total=3, settled_trades_30d=2,
    ))
    await session.commit()

    intent = _intent(sample_market.id, bankroll=7_000.0)
    result = await evaluate(session, intent)
    assert not any(f.check == "drawdown" for f in result.failures)


@pytest.mark.critical
async def test_model_health_fails_closed_when_unknown(session, sample_market, sample_bankroll):
    intent = _intent(sample_market.id, model_healthy=None)
    result = await evaluate(session, intent)
    assert not result.passed
    assert any(f.check == "model_health" for f in result.failures)


@pytest.mark.critical
async def test_model_health_fails_when_unhealthy(session, sample_market, sample_bankroll):
    intent = _intent(sample_market.id, model_healthy=False)
    result = await evaluate(session, intent)
    assert not result.passed
    assert any(f.check == "model_health" for f in result.failures)


@pytest.mark.critical
async def test_market_open_fails_when_market_settled(session, sample_market, sample_bankroll):
    sample_market.status = "settled"
    session.add(sample_market)
    await session.commit()

    result = await evaluate(session, _intent(sample_market.id))
    assert not result.passed
    assert any(f.check == "market_open" for f in result.failures)


@pytest.mark.critical
async def test_market_open_fails_when_market_missing(session, sample_bankroll):
    intent = _intent(uuid4())
    result = await evaluate(session, intent)
    assert not result.passed
    assert any(f.check == "market_open" for f in result.failures)
