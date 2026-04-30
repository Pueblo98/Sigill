"""Portfolio bookkeeping for the backtester.

Tracks cash, open positions, realized PnL, and computes mark-to-market equity
on demand. All math is in float dollars; binary contracts settle at $1 (yes
wins) or $0 (no wins).

Scope (REVIEW-DECISIONS 3C / W2.2(f)): this is an **in-memory backtest-only**
ledger. It does NOT read from or write to the `Position` ORM table. Live and
paper-trading positions are owned by `sigil.execution.oms.OMS`, which is the
single writer of the `positions` table. Keeping these abstractions split
prevents backtest replays from polluting production state.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional
from uuid import UUID

from sigil.backtesting.execution_model import Fill


@dataclass
class PositionState:
    market_id: UUID
    outcome: str
    quantity: int = 0
    avg_entry_price: float = 0.0
    realized_pnl: float = 0.0
    last_mark_price: Optional[float] = None

    @property
    def cost_basis(self) -> float:
        return self.quantity * self.avg_entry_price

    def unrealized_pnl(self) -> float:
        if self.last_mark_price is None or self.quantity == 0:
            return 0.0
        return self.quantity * (self.last_mark_price - self.avg_entry_price)


@dataclass
class Portfolio:
    """Cash + positions ledger. `execute(fill)` mutates state, `equity()`
    returns cash + sum(unrealized + cost basis) for open positions.

    Position keys are (market_id, outcome). Buying increases qty; selling
    reduces and realizes PnL against avg cost.
    """

    initial_cash: float
    cash: float = 0.0
    positions: dict[tuple[UUID, str], PositionState] = field(default_factory=dict)
    realized_pnl_total: float = 0.0
    fees_total: float = 0.0

    def __post_init__(self) -> None:
        self.cash = self.initial_cash

    def execute(self, fill: Fill) -> Optional[float]:
        """Apply a fill. Returns realized PnL from this fill, or None if it
        was a pure entry. Buy increases position and reduces cash by
        qty*price + fees. Sell reduces position, realizes PnL, increases
        cash by qty*price - fees.
        """

        key = (fill.market_id, fill.outcome)
        pos = self.positions.get(key)
        if pos is None:
            pos = PositionState(market_id=fill.market_id, outcome=fill.outcome)
            self.positions[key] = pos

        notional = fill.quantity * fill.price
        self.fees_total += fill.fees
        realized: Optional[float] = None

        if fill.side == "buy":
            new_qty = pos.quantity + fill.quantity
            if pos.quantity >= 0:
                pos.avg_entry_price = (
                    (pos.cost_basis + notional) / new_qty if new_qty != 0 else 0.0
                )
                pos.quantity = new_qty
            else:
                close_qty = min(fill.quantity, -pos.quantity)
                realized = close_qty * (pos.avg_entry_price - fill.price)
                pos.realized_pnl += realized
                self.realized_pnl_total += realized
                pos.quantity += fill.quantity
                if pos.quantity > 0:
                    pos.avg_entry_price = fill.price
                elif pos.quantity == 0:
                    pos.avg_entry_price = 0.0
            self.cash -= notional + fill.fees
        else:
            new_qty = pos.quantity - fill.quantity
            if pos.quantity > 0:
                close_qty = min(fill.quantity, pos.quantity)
                realized = close_qty * (fill.price - pos.avg_entry_price)
                pos.realized_pnl += realized
                self.realized_pnl_total += realized
                pos.quantity -= fill.quantity
                if pos.quantity == 0:
                    pos.avg_entry_price = 0.0
                elif pos.quantity < 0:
                    pos.avg_entry_price = fill.price
            else:
                pos.avg_entry_price = (
                    (abs(pos.quantity) * pos.avg_entry_price + notional)
                    / abs(new_qty)
                    if new_qty != 0
                    else 0.0
                )
                pos.quantity = new_qty
            self.cash += notional - fill.fees

        return realized

    def settle(self, market_id: UUID, settlement_value: float) -> float:
        """Resolve all positions on a market. yes-outcome positions pay
        settlement_value (1.0 or 0.0); no-outcome positions pay (1 - value).
        Returns total realized PnL from this settlement.
        """

        total_realized = 0.0
        keys_to_close = [k for k in self.positions if k[0] == market_id]
        for key in keys_to_close:
            pos = self.positions[key]
            if pos.quantity == 0:
                del self.positions[key]
                continue
            payoff = settlement_value if pos.outcome == "yes" else (1.0 - settlement_value)
            pnl = pos.quantity * (payoff - pos.avg_entry_price)
            self.cash += pos.quantity * payoff
            pos.realized_pnl += pnl
            self.realized_pnl_total += pnl
            total_realized += pnl
            del self.positions[key]
        return total_realized

    def mark_to_market(self, prices: dict[tuple[UUID, str], float]) -> None:
        for key, price in prices.items():
            if key in self.positions:
                self.positions[key].last_mark_price = price

    def equity(self) -> float:
        position_value = 0.0
        for pos in self.positions.values():
            mark = pos.last_mark_price if pos.last_mark_price is not None else pos.avg_entry_price
            position_value += pos.quantity * mark
        return self.cash + position_value

    def to_equity_curve_point(self, ts: datetime) -> tuple[datetime, float]:
        return (ts, self.equity())
