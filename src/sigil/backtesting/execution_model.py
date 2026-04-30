"""Conservative fill modeling for backtests.

Per REVIEW-DECISIONS.md 3C: limits fill only at next-trade-price-or-better,
markets fill at next trade + size-proportional slippage. Live performance may
exceed backtest because real limit orders often fill at touch; biasing
conservative is the right choice for sizing decisions.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional, Protocol
from uuid import UUID, uuid4


LIQUID_VOLUME_THRESHOLD = 10_000.0
BASE_SLIPPAGE_LIQUID_CENTS = 1.0
BASE_SLIPPAGE_ILLIQUID_CENTS = 3.0


@dataclass
class Order:
    """Order request from the strategy to the execution model.

    `limit_price` is required for limit orders, ignored for market/IOC.
    Prices are quoted as probabilities in [0, 1] (cents-per-dollar / 100).
    """

    market_id: UUID
    side: str
    outcome: str
    quantity: int
    order_type: str
    limit_price: Optional[float] = None
    timestamp: Optional[datetime] = None
    client_order_id: str = field(default_factory=lambda: f"sigil_{uuid4()}")

    def __post_init__(self) -> None:
        if self.order_type not in {"limit", "market", "ioc"}:
            raise ValueError(f"unknown order_type: {self.order_type}")
        if self.side not in {"buy", "sell"}:
            raise ValueError(f"unknown side: {self.side}")
        if self.outcome not in {"yes", "no"}:
            raise ValueError(f"unknown outcome: {self.outcome}")
        if self.order_type == "limit" and self.limit_price is None:
            raise ValueError("limit orders require limit_price")
        if self.quantity <= 0:
            raise ValueError("quantity must be positive")


@dataclass
class Fill:
    timestamp: datetime
    market_id: UUID
    side: str
    outcome: str
    quantity: int
    price: float
    fees: float
    client_order_id: str


class ExecutionModel(Protocol):
    """Protocol for fill simulators. Backtester calls `can_fill` once per
    pending order on every event tick."""

    def can_fill(self, order: Order, next_event: "object") -> Optional[Fill]:
        ...


class ConservativeFillModel:
    """Per REVIEW-DECISIONS.md 3C.

    Limit orders fill ONLY when the next observed trade crosses the limit:
      - buy limit at L: fills if next trade price <= L (at trade price, not L)
      - sell limit at L: fills if next trade price >= L
      - if next trade does not cross, the order rests but does not fill in
        this model — multiple consecutive non-crosses still produce no fill
    Market / IOC orders fill at the next trade price plus size-proportional
    slippage. Slippage is 1c base for liquid markets (24h volume > 10k), 3c
    for illiquid, scaled by (size / size_24h_volume).

    Fees are computed per-platform: Kalshi taker fee defaults to $0.07 / contract,
    Polymarket display-only at $0.02 / contract (1C — never auto-traded).
    """

    def __init__(
        self,
        fee_kalshi: float = 0.07,
        fee_polymarket: float = 0.02,
        platform_lookup: Optional[dict] = None,
        liquid_volume_threshold: float = LIQUID_VOLUME_THRESHOLD,
        base_slippage_liquid_cents: float = BASE_SLIPPAGE_LIQUID_CENTS,
        base_slippage_illiquid_cents: float = BASE_SLIPPAGE_ILLIQUID_CENTS,
    ) -> None:
        self.fee_kalshi = fee_kalshi
        self.fee_polymarket = fee_polymarket
        self.platform_lookup = platform_lookup or {}
        self.liquid_volume_threshold = liquid_volume_threshold
        self.base_slippage_liquid_cents = base_slippage_liquid_cents
        self.base_slippage_illiquid_cents = base_slippage_illiquid_cents

    def _fee_for(self, market_id: UUID) -> float:
        platform = self.platform_lookup.get(market_id, "kalshi")
        if platform == "polymarket":
            return self.fee_polymarket
        return self.fee_kalshi

    def can_fill(self, order: Order, next_event) -> Optional[Fill]:
        from sigil.backtesting.engine import PriceTick

        if not isinstance(next_event, PriceTick):
            return None
        if next_event.market_id != order.market_id:
            return None
        if next_event.trade_price is None:
            return None

        trade_price = float(next_event.trade_price)

        if order.order_type == "limit":
            limit = float(order.limit_price)
            if order.side == "buy" and trade_price > limit:
                return None
            if order.side == "sell" and trade_price < limit:
                return None
            fill_price = trade_price
        else:
            slippage = self._compute_slippage(order, next_event)
            if order.side == "buy":
                fill_price = min(1.0, trade_price + slippage)
            else:
                fill_price = max(0.0, trade_price - slippage)

        fees = self._fee_for(order.market_id) * order.quantity

        return Fill(
            timestamp=next_event.timestamp,
            market_id=order.market_id,
            side=order.side,
            outcome=order.outcome,
            quantity=order.quantity,
            price=fill_price,
            fees=fees,
            client_order_id=order.client_order_id,
        )

    def _compute_slippage(self, order: Order, tick) -> float:
        volume_24h = float(tick.volume_24h or 0.0)
        if volume_24h > self.liquid_volume_threshold:
            base_cents = self.base_slippage_liquid_cents
        else:
            base_cents = self.base_slippage_illiquid_cents

        if volume_24h > 0:
            scale = max(1.0, order.quantity / volume_24h)
        else:
            scale = max(1.0, float(order.quantity))

        slippage_cents = base_cents * scale
        return slippage_cents / 100.0
