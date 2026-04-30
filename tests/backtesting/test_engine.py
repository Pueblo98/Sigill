"""Backtester determinism + edge cases."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Optional
from uuid import uuid4

import pytest

from sigil.backtesting.engine import (
    BacktestConfig,
    Backtester,
    PriceTick,
    SettlementEvent,
    Signal,
)


class _BuyOnceStrategy:
    """Issues a single limit buy signal on the first tick we see."""

    def __init__(self, market_id, limit_price=0.45):
        self.market_id = market_id
        self.limit_price = limit_price
        self._fired = False

    def generate_signals(self, event, portfolio_state):
        if self._fired:
            return []
        if isinstance(event, PriceTick):
            self._fired = True
            return [
                Signal(
                    market_id=self.market_id,
                    side="buy",
                    outcome="yes",
                    quantity=10,
                    order_type="limit",
                    limit_price=self.limit_price,
                )
            ]
        return []


def _events(market_id, prices, *, vol=50_000.0):
    base = datetime(2026, 1, 1, 12, 0, 0)
    return [
        PriceTick(
            timestamp=base + timedelta(minutes=i),
            market_id=market_id,
            trade_price=p,
            volume_24h=vol,
        )
        for i, p in enumerate(prices)
    ]


def _config(start, end):
    return BacktestConfig(start_date=start, end_date=end, initial_capital=5000.0)


def test_engine_deterministic_same_inputs():
    market_id = uuid4()
    events = _events(market_id, [0.50, 0.44, 0.46, 0.48])
    cfg = _config(events[0].timestamp, events[-1].timestamp)

    res_a = Backtester(_BuyOnceStrategy(market_id), list(events), cfg).run()
    res_b = Backtester(_BuyOnceStrategy(market_id), list(events), cfg).run()

    assert len(res_a.trades) == len(res_b.trades)
    for ta, tb in zip(res_a.trades, res_b.trades):
        assert ta.fill_price == tb.fill_price
        assert ta.quantity == tb.quantity
        assert ta.realized_pnl == tb.realized_pnl
    assert res_a.equity_curve == res_b.equity_curve


def test_engine_empty_data():
    market_id = uuid4()
    cfg = _config(datetime(2026, 1, 1), datetime(2026, 2, 1))
    res = Backtester(_BuyOnceStrategy(market_id), [], cfg).run()
    assert res.trades == []
    assert res.equity_curve == []
    assert res.final_equity == 5000.0


def test_engine_single_tick_signal_does_not_fill():
    """A signal issued on the only tick has no future tick to fill against."""
    market_id = uuid4()
    events = _events(market_id, [0.50])
    cfg = _config(events[0].timestamp, events[-1].timestamp)
    res = Backtester(_BuyOnceStrategy(market_id), events, cfg).run()
    assert res.trades == []
    assert res.equity_curve[0][1] == pytest.approx(5000.0)


def test_engine_settlement_realizes_position():
    """Buy at 0.40, settle at 1.0 -> realized PnL = qty * (1.0 - 0.40)."""
    market_id = uuid4()
    base = datetime(2026, 1, 1, 12, 0, 0)
    events = [
        PriceTick(timestamp=base, market_id=market_id, trade_price=0.50, volume_24h=50_000.0),
        PriceTick(timestamp=base + timedelta(minutes=1), market_id=market_id,
                  trade_price=0.40, volume_24h=50_000.0),
        SettlementEvent(timestamp=base + timedelta(hours=1), market_id=market_id,
                        settlement_value=1.0),
    ]
    cfg = _config(base, base + timedelta(hours=2))
    strat = _BuyOnceStrategy(market_id, limit_price=0.45)
    res = Backtester(strat, events, cfg).run()
    fills = [t for t in res.trades if t.side == "buy"]
    settles = [t for t in res.trades if t.side == "settle"]
    assert len(fills) == 1
    assert fills[0].fill_price == pytest.approx(0.40)
    assert len(settles) == 1
    expected_realized = 10 * (1.0 - 0.40)
    assert settles[0].realized_pnl == pytest.approx(expected_realized)


def test_engine_excludes_events_outside_window():
    market_id = uuid4()
    events = _events(market_id, [0.50, 0.40])
    cfg = BacktestConfig(
        start_date=events[0].timestamp + timedelta(minutes=10),
        end_date=events[0].timestamp + timedelta(hours=1),
        initial_capital=5000.0,
    )
    res = Backtester(_BuyOnceStrategy(market_id), events, cfg).run()
    assert res.equity_curve == []
    assert res.trades == []


def test_engine_equity_curve_has_one_point_per_in_window_event():
    market_id = uuid4()
    events = _events(market_id, [0.50, 0.40, 0.45])
    cfg = _config(events[0].timestamp, events[-1].timestamp)
    res = Backtester(_BuyOnceStrategy(market_id), events, cfg).run()
    assert len(res.equity_curve) == 3
