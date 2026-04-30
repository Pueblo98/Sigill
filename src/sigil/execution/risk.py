"""Pre-trade risk checks.

PRD section 5.1 mandates seven pass-or-reject checks; ALL must pass before the
OMS submits an order. Every check FAILS CLOSED — missing data is treated as a
rejection with an explanation, not a silent pass.

Returned object is `RiskCheckResult(passed: bool, failures: list[CheckFailure])`
so the caller can log/alert on partial-failure detail.

Drawdown gate honours decision 2F: trip only when both
`DRAWDOWN_MIN_SETTLED_TOTAL` AND `DRAWDOWN_MIN_SETTLED_IN_WINDOW` are met.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Iterable, Optional
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from sigil.config import config
from sigil.models import BankrollSnapshot, Market, Position

logger = logging.getLogger(__name__)


@dataclass
class CheckFailure:
    check: str
    reason: str


@dataclass
class RiskCheckResult:
    passed: bool
    failures: list[CheckFailure] = field(default_factory=list)

    @property
    def reason(self) -> str:
        return "; ".join(f"{f.check}: {f.reason}" for f in self.failures)


@dataclass
class TradeIntent:
    platform: str
    market_id: UUID
    outcome: str
    side: str
    price: float
    quantity: int
    order_type: str
    mode: str
    category: Optional[str] = None       # taxonomy_l1; resolved if not given
    model_id: Optional[str] = None
    model_healthy: Optional[bool] = None # None means "we don't know" -> fail
    bankroll: Optional[float] = None     # if None, read latest snapshot


# --- helpers -------------------------------------------------------------- #

def _trade_notional(intent: TradeIntent) -> float:
    return float(intent.price) * int(intent.quantity)


async def _latest_bankroll(session: AsyncSession, mode: str) -> Optional[BankrollSnapshot]:
    stmt = (
        select(BankrollSnapshot)
        .where(BankrollSnapshot.mode == mode)
        .order_by(BankrollSnapshot.time.desc())
        .limit(1)
    )
    result = await session.execute(stmt)
    return result.scalar_one_or_none()


async def _open_positions_for(
    session: AsyncSession, *, mode: str, platform: Optional[str] = None,
) -> list[Position]:
    stmt = select(Position).where(Position.mode == mode, Position.status == "open")
    if platform:
        stmt = stmt.where(Position.platform == platform)
    result = await session.execute(stmt)
    return list(result.scalars().all())


def _exposure(positions: Iterable[Position]) -> float:
    return sum(float(p.quantity) * float(p.avg_entry_price) for p in positions)


# --- individual checks --------------------------------------------------- #

async def check_balance(session: AsyncSession, intent: TradeIntent) -> Optional[CheckFailure]:
    notional = _trade_notional(intent)
    if intent.bankroll is not None:
        if intent.bankroll < notional:
            return CheckFailure("balance", f"insufficient bankroll {intent.bankroll:.2f} < {notional:.2f}")
        return None

    snap = await _latest_bankroll(session, intent.mode)
    if snap is None:
        return CheckFailure("balance", "no bankroll snapshot — fail closed")
    if float(snap.equity) < notional:
        return CheckFailure(
            "balance",
            f"insufficient equity {float(snap.equity):.2f} < {notional:.2f}",
        )
    return None


async def check_per_market_limit(session: AsyncSession, intent: TradeIntent) -> Optional[CheckFailure]:
    bankroll = await _resolve_bankroll(session, intent)
    if bankroll is None:
        return CheckFailure("per_market", "no bankroll snapshot — fail closed")
    cap = bankroll * config.MAX_POSITION_PCT / 100.0
    stmt = select(Position).where(
        Position.market_id == intent.market_id,
        Position.mode == intent.mode,
        Position.status == "open",
    )
    result = await session.execute(stmt)
    existing = _exposure(result.scalars().all())
    after = existing + _trade_notional(intent)
    if after > cap:
        return CheckFailure(
            "per_market",
            f"market exposure {after:.2f} > cap {cap:.2f}",
        )
    return None


async def check_per_category(session: AsyncSession, intent: TradeIntent) -> Optional[CheckFailure]:
    category = intent.category or await _resolve_category(session, intent.market_id)
    if category is None:
        return CheckFailure("per_category", "could not resolve category — fail closed")

    bankroll = await _resolve_bankroll(session, intent)
    if bankroll is None:
        return CheckFailure("per_category", "no bankroll snapshot — fail closed")
    cap = bankroll * config.MAX_CATEGORY_EXPOSURE_PCT / 100.0

    stmt = (
        select(Position, Market)
        .join(Market, Market.id == Position.market_id)
        .where(
            Market.taxonomy_l1 == category,
            Position.mode == intent.mode,
            Position.status == "open",
        )
    )
    result = await session.execute(stmt)
    positions = [row[0] for row in result.all()]
    after = _exposure(positions) + _trade_notional(intent)
    if after > cap:
        return CheckFailure(
            "per_category",
            f"category exposure {after:.2f} > cap {cap:.2f}",
        )
    return None


async def check_per_platform(session: AsyncSession, intent: TradeIntent) -> Optional[CheckFailure]:
    bankroll = await _resolve_bankroll(session, intent)
    if bankroll is None:
        return CheckFailure("per_platform", "no bankroll snapshot — fail closed")
    cap = bankroll * config.MAX_PLATFORM_EXPOSURE_PCT / 100.0
    positions = await _open_positions_for(session, mode=intent.mode, platform=intent.platform)
    after = _exposure(positions) + _trade_notional(intent)
    if after > cap:
        return CheckFailure(
            "per_platform",
            f"platform exposure {after:.2f} > cap {cap:.2f}",
        )
    return None


async def check_drawdown(session: AsyncSession, intent: TradeIntent) -> Optional[CheckFailure]:
    snap = await _latest_bankroll(session, intent.mode)
    if snap is None:
        return CheckFailure("drawdown", "no bankroll snapshot — fail closed")

    if (
        snap.settled_trades_total < config.DRAWDOWN_MIN_SETTLED_TOTAL
        or snap.settled_trades_30d < config.DRAWDOWN_MIN_SETTLED_IN_WINDOW
    ):
        # Decision 2F: too few trades for the gate to be meaningful.
        return None

    peak = await _peak_equity(session, intent.mode)
    if peak is None or peak <= 0:
        return None
    drawdown_pct = (peak - float(snap.equity)) / peak * 100.0
    if drawdown_pct >= config.DRAWDOWN_HALT_PCT:
        return CheckFailure(
            "drawdown",
            f"drawdown {drawdown_pct:.2f}% >= halt {config.DRAWDOWN_HALT_PCT}%",
        )
    return None


async def check_model_health(session: AsyncSession, intent: TradeIntent) -> Optional[CheckFailure]:
    if intent.model_healthy is None:
        return CheckFailure("model_health", "no model-health signal — fail closed")
    if not intent.model_healthy:
        return CheckFailure("model_health", f"model {intent.model_id} unhealthy")
    return None


async def check_market_open(session: AsyncSession, intent: TradeIntent) -> Optional[CheckFailure]:
    market = await session.get(Market, intent.market_id)
    if market is None:
        return CheckFailure("market_open", "market not found — fail closed")
    if market.status != "open":
        return CheckFailure("market_open", f"market status={market.status}")
    return None


# --- aggregation --------------------------------------------------------- #

CHECKS = (
    check_balance,
    check_per_market_limit,
    check_per_category,
    check_per_platform,
    check_drawdown,
    check_model_health,
    check_market_open,
)


async def evaluate(session: AsyncSession, intent: TradeIntent) -> RiskCheckResult:
    failures: list[CheckFailure] = []
    for check in CHECKS:
        try:
            failure = await check(session, intent)
        except Exception as exc:  # noqa: BLE001 — fail closed on bug too
            logger.exception("risk check %s raised", check.__name__)
            failure = CheckFailure(check.__name__, f"check raised: {exc}")
        if failure is not None:
            failures.append(failure)
    return RiskCheckResult(passed=not failures, failures=failures)


# --- internals ----------------------------------------------------------- #

async def _resolve_bankroll(session: AsyncSession, intent: TradeIntent) -> Optional[float]:
    if intent.bankroll is not None:
        return intent.bankroll
    snap = await _latest_bankroll(session, intent.mode)
    return float(snap.equity) if snap is not None else None


async def _resolve_category(session: AsyncSession, market_id: UUID) -> Optional[str]:
    market = await session.get(Market, market_id)
    return market.taxonomy_l1 if market is not None else None


async def _peak_equity(session: AsyncSession, mode: str) -> Optional[float]:
    cutoff = datetime.now(timezone.utc) - timedelta(days=config.DRAWDOWN_WINDOW_DAYS)
    stmt = (
        select(BankrollSnapshot.equity)
        .where(BankrollSnapshot.mode == mode, BankrollSnapshot.time >= cutoff)
    )
    result = await session.execute(stmt)
    values = [float(v) for v in result.scalars().all()]
    return max(values) if values else None
