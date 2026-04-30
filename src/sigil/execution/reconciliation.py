"""Position reconciliation with hysteresis (REVIEW-DECISIONS 1D).

Compares exchange-reported positions to the local positions table. Each call to
`observe()` writes a row to `reconciliation_observations`. We only apply
"exchange overrides local" when the exchange has agreed with itself across
`config.RECONCILIATION_HYSTERESIS_MATCHES` consecutive observations.

While the two sides disagree, we:
  - alert (logger.warning is sufficient for now; Telegram routing is Lane B's
    severity-channel concern),
  - freeze new orders for that market via an in-memory flag that other code
    (OMS / decision engine) can consult.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Optional
from uuid import UUID, uuid4

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from sigil.config import config
from sigil.models import Position, ReconciliationObservation

logger = logging.getLogger(__name__)


@dataclass
class ExchangePosition:
    platform: str
    market_id: UUID
    outcome: str
    quantity: int


@dataclass
class ObservationOutcome:
    is_match: bool
    consecutive_matches: int
    overrode_local: bool
    frozen: bool
    note: str = ""


# In-process freeze set. (market_id, outcome) tuples here are blocked from new
# orders until the next match. Survives only as long as the process; that is
# intentional — a restart triggers a fresh observation cycle anyway.
_FROZEN: set[tuple[str, UUID, str]] = set()


def is_frozen(platform: str, market_id: UUID, outcome: str) -> bool:
    return (platform, market_id, outcome) in _FROZEN


def freeze(platform: str, market_id: UUID, outcome: str) -> None:
    _FROZEN.add((platform, market_id, outcome))


def unfreeze(platform: str, market_id: UUID, outcome: str) -> None:
    _FROZEN.discard((platform, market_id, outcome))


def _key(p: str, m: UUID, o: str) -> tuple[str, UUID, str]:
    return (p, m, o)


class ReconciliationTracker:
    def __init__(self, session: AsyncSession, hysteresis: Optional[int] = None) -> None:
        self.session = session
        self.hysteresis = hysteresis or config.RECONCILIATION_HYSTERESIS_MATCHES

    async def observe(self, exchange: ExchangePosition) -> ObservationOutcome:
        """Record one observation.

        Hysteresis tracks how many *consecutive* exchange reports agree with
        each other (REVIEW-DECISIONS 1D — "3 consecutive consistent observations").
        Override is applied once that window is met; if local already agrees
        the override is a no-op. While the exchange is flapping (disagrees with
        the prior exchange report) we freeze new orders for that market and
        emit an alert.
        """
        local = await self._local_position(exchange)
        local_qty = int(local.quantity) if local else 0

        prev = await self._most_recent_observation(exchange)
        if prev is None or int(prev.exchange_qty) != exchange.quantity:
            consec = 1
            exchange_stable = prev is None or int(prev.exchange_qty) == exchange.quantity
        else:
            consec = int(prev.consecutive_matches) + 1
            exchange_stable = True

        is_match = local_qty == exchange.quantity

        obs = ReconciliationObservation(
            id=uuid4(),
            observed_at=datetime.now(timezone.utc),
            platform=exchange.platform,
            market_id=exchange.market_id,
            outcome=exchange.outcome,
            exchange_qty=exchange.quantity,
            local_qty=local_qty,
            is_match=is_match,
            consecutive_matches=consec,
        )
        self.session.add(obs)

        outcome = ObservationOutcome(
            is_match=is_match,
            consecutive_matches=consec,
            overrode_local=False,
            frozen=False,
        )

        if not is_match and not exchange_stable:
            freeze(exchange.platform, exchange.market_id, exchange.outcome)
            outcome.frozen = True
            outcome.note = (
                f"local={local_qty} exchange={exchange.quantity} "
                f"flapping (consec={consec})"
            )
            logger.warning(
                "reconciliation flapping on %s/%s/%s: %s",
                exchange.platform, exchange.market_id, exchange.outcome, outcome.note,
            )
            return outcome

        if not is_match:
            # Stable disagreement: freeze new orders until hysteresis is met.
            freeze(exchange.platform, exchange.market_id, exchange.outcome)
            outcome.frozen = True
            outcome.note = (
                f"local={local_qty} exchange={exchange.quantity} "
                f"(stable, consec={consec})"
            )
            logger.warning(
                "reconciliation mismatch on %s/%s/%s: %s",
                exchange.platform, exchange.market_id, exchange.outcome, outcome.note,
            )

        if consec >= self.hysteresis:
            await self._apply_override(local, exchange)
            unfreeze(exchange.platform, exchange.market_id, exchange.outcome)
            outcome.overrode_local = True
            outcome.frozen = False
            outcome.note = f"override applied after {consec} consistent exchange observations"
        return outcome

    async def _local_position(self, exchange: ExchangePosition) -> Optional[Position]:
        stmt = select(Position).where(
            Position.platform == exchange.platform,
            Position.market_id == exchange.market_id,
            Position.outcome == exchange.outcome,
            Position.mode == "live",
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def _most_recent_observation(self, exchange: ExchangePosition) -> Optional[ReconciliationObservation]:
        stmt = (
            select(ReconciliationObservation)
            .where(
                ReconciliationObservation.platform == exchange.platform,
                ReconciliationObservation.market_id == exchange.market_id,
                ReconciliationObservation.outcome == exchange.outcome,
            )
            .order_by(ReconciliationObservation.observed_at.desc())
            .limit(1)
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def _apply_override(self, local: Optional[Position], exchange: ExchangePosition) -> None:
        if exchange.quantity == 0:
            if local is not None:
                local.quantity = 0
                local.status = "closed"
                local.closed_at = datetime.now(timezone.utc)
                self.session.add(local)
            return
        if local is None:
            local = Position(
                id=uuid4(),
                platform=exchange.platform,
                market_id=exchange.market_id,
                mode="live",
                outcome=exchange.outcome,
                quantity=exchange.quantity,
                avg_entry_price=0.0,
                status="open",
            )
        else:
            local.quantity = exchange.quantity
            local.status = "open"
        self.session.add(local)


def reset_freeze_state() -> None:
    """Test helper — clears the in-process freeze set."""
    _FROZEN.clear()
