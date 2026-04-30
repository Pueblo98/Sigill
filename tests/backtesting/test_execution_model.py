"""Conservative-fill scenarios. Critical per REVIEW-DECISIONS.md 3B."""

from __future__ import annotations

from datetime import datetime, timedelta
from uuid import uuid4

import pytest

from sigil.backtesting.engine import PriceTick
from sigil.backtesting.execution_model import ConservativeFillModel, Order


@pytest.fixture
def model() -> ConservativeFillModel:
    return ConservativeFillModel(fee_kalshi=0.07, fee_polymarket=0.02)


@pytest.fixture
def market_id():
    return uuid4()


def _tick(market_id, *, price=None, vol=20_000.0):
    return PriceTick(
        timestamp=datetime(2026, 1, 1, 12, 0, 0),
        market_id=market_id,
        trade_price=price,
        volume_24h=vol,
    )


@pytest.mark.critical
def test_buy_limit_fills_when_next_trade_is_better(model, market_id):
    """Buy limit at 0.42, next trade at 0.41 -> fills at 0.41 (limit-or-better)."""
    order = Order(market_id=market_id, side="buy", outcome="yes", quantity=10,
                  order_type="limit", limit_price=0.42)
    fill = model.can_fill(order, _tick(market_id, price=0.41))
    assert fill is not None
    assert fill.price == pytest.approx(0.41)
    assert fill.quantity == 10


@pytest.mark.critical
def test_buy_limit_does_not_fill_when_next_trade_above(model, market_id):
    """Buy limit at 0.42, next trade at 0.43 -> no fill."""
    order = Order(market_id=market_id, side="buy", outcome="yes", quantity=10,
                  order_type="limit", limit_price=0.42)
    fill = model.can_fill(order, _tick(market_id, price=0.43))
    assert fill is None


@pytest.mark.critical
def test_buy_limit_fills_at_touch(model, market_id):
    """Buy limit at 0.42, next trade at 0.42 -> fills at 0.42."""
    order = Order(market_id=market_id, side="buy", outcome="yes", quantity=10,
                  order_type="limit", limit_price=0.42)
    fill = model.can_fill(order, _tick(market_id, price=0.42))
    assert fill is not None
    assert fill.price == pytest.approx(0.42)


@pytest.mark.critical
def test_sell_limit_does_not_fill_when_next_trade_below(model, market_id):
    order = Order(market_id=market_id, side="sell", outcome="yes", quantity=10,
                  order_type="limit", limit_price=0.55)
    assert model.can_fill(order, _tick(market_id, price=0.54)) is None


@pytest.mark.critical
def test_sell_limit_fills_when_next_trade_above(model, market_id):
    order = Order(market_id=market_id, side="sell", outcome="yes", quantity=10,
                  order_type="limit", limit_price=0.55)
    fill = model.can_fill(order, _tick(market_id, price=0.56))
    assert fill is not None
    assert fill.price == pytest.approx(0.56)


@pytest.mark.critical
def test_market_order_liquid_small_size_one_cent(model, market_id):
    """Liquid market (24h vol > 10k), small size -> next trade + 1c."""
    order = Order(market_id=market_id, side="buy", outcome="yes", quantity=10,
                  order_type="market")
    fill = model.can_fill(order, _tick(market_id, price=0.50, vol=50_000.0))
    assert fill is not None
    assert fill.price == pytest.approx(0.51)


@pytest.mark.critical
def test_market_order_illiquid_three_cents(model, market_id):
    """Illiquid (24h vol below threshold), small size -> next trade + 3c."""
    order = Order(market_id=market_id, side="buy", outcome="yes", quantity=10,
                  order_type="market")
    fill = model.can_fill(order, _tick(market_id, price=0.50, vol=5_000.0))
    assert fill is not None
    assert fill.price == pytest.approx(0.53)


@pytest.mark.critical
def test_market_order_illiquid_large_size_scales_up(model, market_id):
    """Size > 24h volume scales slippage proportionally above the base."""
    order = Order(market_id=market_id, side="buy", outcome="yes", quantity=20_000,
                  order_type="market")
    fill = model.can_fill(order, _tick(market_id, price=0.50, vol=5_000.0))
    assert fill is not None
    assert fill.price > 0.53


def test_sell_market_subtracts_slippage(model, market_id):
    order = Order(market_id=market_id, side="sell", outcome="yes", quantity=10,
                  order_type="market")
    fill = model.can_fill(order, _tick(market_id, price=0.50, vol=50_000.0))
    assert fill is not None
    assert fill.price == pytest.approx(0.49)


def test_fill_skips_unrelated_market(model, market_id):
    other = uuid4()
    order = Order(market_id=market_id, side="buy", outcome="yes", quantity=10,
                  order_type="market")
    fill = model.can_fill(order, _tick(other, price=0.50))
    assert fill is None


def test_fill_skips_tick_without_trade_price(model, market_id):
    order = Order(market_id=market_id, side="buy", outcome="yes", quantity=10,
                  order_type="market")
    fill = model.can_fill(order, _tick(market_id, price=None))
    assert fill is None


def test_fees_use_polymarket_when_marked(market_id):
    model = ConservativeFillModel(
        fee_kalshi=0.07, fee_polymarket=0.02,
        platform_lookup={market_id: "polymarket"},
    )
    order = Order(market_id=market_id, side="buy", outcome="yes", quantity=10,
                  order_type="market")
    fill = model.can_fill(order, _tick(market_id, price=0.50, vol=50_000.0))
    assert fill.fees == pytest.approx(0.02 * 10)


def test_order_validation_rejects_bad_inputs(market_id):
    with pytest.raises(ValueError):
        Order(market_id=market_id, side="buy", outcome="yes", quantity=10,
              order_type="limit")  # missing limit_price
    with pytest.raises(ValueError):
        Order(market_id=market_id, side="buy", outcome="maybe", quantity=10,
              order_type="market")
    with pytest.raises(ValueError):
        Order(market_id=market_id, side="buy", outcome="yes", quantity=0,
              order_type="market")
