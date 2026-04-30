"""Event-driven backtester.

PRD §4.3: chronological replay of price ticks + settlement events. Strategy
emits orders, execution model decides fills against the *next* tick (3C),
portfolio applies them, equity curve is recorded after every event.

Determinism: same inputs, same ordering, same metrics. No clock-time, no
randomness, no async. Tie-break events sharing a timestamp by their index in
the input iterable.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Iterable, Iterator, Optional, Protocol
from uuid import UUID

from sigil.backtesting.execution_model import (
    ConservativeFillModel,
    ExecutionModel,
    Fill,
    Order,
)
from sigil.backtesting.portfolio import Portfolio


@dataclass
class PriceTick:
    timestamp: datetime
    market_id: UUID
    bid: Optional[float] = None
    ask: Optional[float] = None
    trade_price: Optional[float] = None
    volume_24h: Optional[float] = None


@dataclass
class SettlementEvent:
    timestamp: datetime
    market_id: UUID
    settlement_value: float


Event = PriceTick | SettlementEvent


@dataclass
class Signal:
    """Emitted by Strategy. Lower-level than an exchange order — the engine
    converts it into an `Order` after applying portfolio guards."""

    market_id: UUID
    side: str
    outcome: str
    quantity: int
    order_type: str = "limit"
    limit_price: Optional[float] = None


class Strategy(Protocol):
    def generate_signals(self, event: Event, portfolio_state: Portfolio) -> list[Signal]:
        ...


@dataclass
class BacktestConfig:
    start_date: datetime
    end_date: datetime
    initial_capital: float = 5000.0
    fee_kalshi: float = 0.07
    fee_polymarket: float = 0.02


@dataclass
class Trade:
    timestamp: datetime
    market_id: UUID
    side: str
    outcome: str
    quantity: int
    fill_price: float
    fees: float
    realized_pnl: Optional[float] = None
    market_price_at_entry: Optional[float] = None


@dataclass
class BacktestResult:
    config: BacktestConfig
    trades: list[Trade]
    equity_curve: list[tuple[datetime, float]]
    final_equity: float
    metrics: dict = field(default_factory=dict)


class Backtester:
    """Drives a `Strategy` against an iterable of `Event`s.

    On each event:
      1. Try to fill any pending orders against this event (per 3C the
         execution model needs the *next* trade — pending orders carry
         over).
      2. If event is a settlement, settle the market in the portfolio.
      3. Mark portfolio to market with the event's last/trade price.
      4. Record an equity-curve point.
      5. Ask the strategy for new signals; queue them as pending orders.

    Pending orders that are still unfilled at end-of-stream are dropped — we
    only credit fills we can prove against historical data (3C).
    """

    def __init__(
        self,
        strategy: Strategy,
        data_iter: Iterable[Event],
        config: BacktestConfig,
        execution_model: Optional[ExecutionModel] = None,
    ) -> None:
        self.strategy = strategy
        self.data_iter = data_iter
        self.config = config
        self.execution_model = execution_model or ConservativeFillModel(
            fee_kalshi=config.fee_kalshi, fee_polymarket=config.fee_polymarket
        )
        self.portfolio = Portfolio(initial_cash=config.initial_capital)
        self._pending: list[Order] = []
        self._trades: list[Trade] = []
        self._equity_curve: list[tuple[datetime, float]] = []
        self._fill_to_entry_price: dict[str, float] = {}

    def run(self) -> BacktestResult:
        ordered_events = self._sorted_events()
        for event in ordered_events:
            self._process_fills(event)
            if isinstance(event, SettlementEvent):
                self._handle_settlement(event)
            else:
                self._handle_tick(event)
            self._equity_curve.append(self.portfolio.to_equity_curve_point(event.timestamp))
            for signal in self.strategy.generate_signals(event, self.portfolio):
                self._pending.append(self._signal_to_order(signal, event.timestamp))

        return BacktestResult(
            config=self.config,
            trades=self._trades,
            equity_curve=self._equity_curve,
            final_equity=self.portfolio.equity(),
        )

    def _sorted_events(self) -> Iterator[Event]:
        events = list(self.data_iter)
        events.sort(key=lambda e: (e.timestamp, 0 if isinstance(e, PriceTick) else 1))
        for e in events:
            if e.timestamp < self.config.start_date or e.timestamp > self.config.end_date:
                continue
            yield e

    def _process_fills(self, event: Event) -> None:
        if not self._pending:
            return
        still_pending: list[Order] = []
        for order in self._pending:
            fill = self.execution_model.can_fill(order, event)
            if fill is None:
                still_pending.append(order)
            else:
                self._apply_fill(fill, order)
        self._pending = still_pending

    def _apply_fill(self, fill: Fill, order: Order) -> None:
        realized = self.portfolio.execute(fill)
        entry_price = self._fill_to_entry_price.get(order.client_order_id)
        self._trades.append(
            Trade(
                timestamp=fill.timestamp,
                market_id=fill.market_id,
                side=fill.side,
                outcome=fill.outcome,
                quantity=fill.quantity,
                fill_price=fill.price,
                fees=fill.fees,
                realized_pnl=realized,
                market_price_at_entry=entry_price,
            )
        )

    def _handle_settlement(self, event: SettlementEvent) -> None:
        realized = self.portfolio.settle(event.market_id, event.settlement_value)
        if realized != 0.0:
            self._trades.append(
                Trade(
                    timestamp=event.timestamp,
                    market_id=event.market_id,
                    side="settle",
                    outcome="yes" if event.settlement_value >= 0.5 else "no",
                    quantity=0,
                    fill_price=event.settlement_value,
                    fees=0.0,
                    realized_pnl=realized,
                )
            )

    def _handle_tick(self, event: PriceTick) -> None:
        mark_price = event.trade_price
        if mark_price is None and event.bid is not None and event.ask is not None:
            mark_price = (float(event.bid) + float(event.ask)) / 2.0
        if mark_price is None:
            return
        prices: dict[tuple[UUID, str], float] = {}
        for outcome in ("yes", "no"):
            key = (event.market_id, outcome)
            if key in self.portfolio.positions:
                prices[key] = float(mark_price) if outcome == "yes" else 1.0 - float(mark_price)
        if prices:
            self.portfolio.mark_to_market(prices)

    def _signal_to_order(self, signal: Signal, ts: datetime) -> Order:
        order = Order(
            market_id=signal.market_id,
            side=signal.side,
            outcome=signal.outcome,
            quantity=signal.quantity,
            order_type=signal.order_type,
            limit_price=signal.limit_price,
            timestamp=ts,
        )
        if signal.limit_price is not None:
            self._fill_to_entry_price[order.client_order_id] = signal.limit_price
        return order
