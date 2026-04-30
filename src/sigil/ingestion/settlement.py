"""Kalshi settlement: WebSocket event-driven + hourly polling fallback.

Decision 1G: subscribe to the Kalshi market-status WS channel; on
`status: settled`, close matching `Position`s, write realized P&L, append a
fresh `BankrollSnapshot`. An APScheduler job sweeps every
`config.SETTLEMENT_FALLBACK_POLL_INTERVAL_SECONDS` to catch missed events.

The actual Kalshi REST/WS shape is best-effort here — we keep the public
surface small (`SettlementEvent` + `SettlementHandler`) so tests can drive it
with synthetic events even if the upstream wire format shifts.
"""
from __future__ import annotations

import asyncio
import json
import logging
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import AsyncIterator, Iterable, Optional, Protocol
from uuid import UUID, uuid4

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from sigil.config import config
from sigil.models import BankrollSnapshot, Market, Position

logger = logging.getLogger(__name__)


@dataclass
class SettlementEvent:
    platform: str
    external_id: str
    settlement_value: float        # 0..1; 1.0 = YES wins, 0.0 = NO wins
    settled_at: datetime


class SettlementSource(Protocol):
    """Anything that can yield SettlementEvents — Kalshi WS in prod, fake in tests."""

    async def stream_settlements(self) -> AsyncIterator[SettlementEvent]:
        ...

    async def fetch_status(self, external_id: str) -> Optional[SettlementEvent]:
        ...


class SettlementHandler:
    def __init__(self, session_factory) -> None:
        self.session_factory = session_factory

    async def apply(self, event: SettlementEvent) -> int:
        """Settle every open position for the given market. Returns count settled."""
        async with self.session_factory() as session:
            market = await self._market(session, event.platform, event.external_id)
            if market is None:
                logger.warning(
                    "settlement for unknown %s/%s — ignoring",
                    event.platform, event.external_id,
                )
                return 0

            market.status = "settled"
            market.settlement_value = event.settlement_value
            session.add(market)

            stmt = select(Position).where(
                Position.market_id == market.id,
                Position.status == "open",
            )
            result = await session.execute(stmt)
            positions = list(result.scalars().all())
            settled = 0
            total_realized = 0.0
            for pos in positions:
                payoff = self._payoff(pos.outcome, event.settlement_value)
                pnl_per_contract = payoff - float(pos.avg_entry_price)
                realized = pnl_per_contract * int(pos.quantity)
                pos.realized_pnl = float(pos.realized_pnl or 0.0) + realized
                pos.unrealized_pnl = 0.0
                pos.current_price = payoff
                pos.status = "closed"
                pos.closed_at = event.settled_at
                pos.quantity = 0
                session.add(pos)
                total_realized += realized
                settled += 1

            if settled:
                await self._append_bankroll_snapshot(session, total_realized)
                logger.info(
                    "settled %d positions on %s/%s (realized=%.2f)",
                    settled, event.platform, event.external_id, total_realized,
                )
            await session.commit()
            return settled

    async def _market(self, session: AsyncSession, platform: str, external_id: str) -> Optional[Market]:
        stmt = select(Market).where(
            Market.platform == platform, Market.external_id == external_id
        )
        result = await session.execute(stmt)
        return result.scalar_one_or_none()

    @staticmethod
    def _payoff(outcome: str, settlement_value: float) -> float:
        if outcome == "yes":
            return float(settlement_value)
        if outcome == "no":
            return 1.0 - float(settlement_value)
        raise ValueError(f"unknown outcome {outcome!r}")

    async def _append_bankroll_snapshot(self, session: AsyncSession, delta_realized: float) -> None:
        # Update both paper and live snapshots independently so each mode tracks
        # its own bankroll. Most callers only run one mode at a time.
        for mode in ("paper", "live"):
            stmt = (
                select(BankrollSnapshot)
                .where(BankrollSnapshot.mode == mode)
                .order_by(BankrollSnapshot.time.desc())
                .limit(1)
            )
            result = await session.execute(stmt)
            prev = result.scalar_one_or_none()
            if prev is None:
                continue
            snap = BankrollSnapshot(
                time=datetime.now(timezone.utc),
                mode=mode,
                equity=float(prev.equity) + delta_realized,
                realized_pnl_total=float(prev.realized_pnl_total) + delta_realized,
                unrealized_pnl_total=float(prev.unrealized_pnl_total),
                settled_trades_total=int(prev.settled_trades_total) + 1,
                settled_trades_30d=int(prev.settled_trades_30d) + 1,
            )
            session.add(snap)


class KalshiSettlementStream:
    """Lightweight wrapper over the Kalshi market-status WebSocket channel.

    Implementation note: the WS frame shape upstream isn't fully stable so we
    only assume the presence of `status`, `market_ticker`, and either
    `settlement_value` or `result`.
    """

    def __init__(self, ws_url: str = "wss://trading-api.kalshi.com/trade-api/ws/v2") -> None:
        self.ws_url = ws_url

    async def stream_settlements(self) -> AsyncIterator[SettlementEvent]:  # pragma: no cover - network
        import websockets  # local import keeps tests import-light

        async with websockets.connect(self.ws_url) as ws:
            await ws.send(json.dumps({
                "id": 1,
                "cmd": "subscribe",
                "params": {"channels": ["market_status"]},
            }))
            async for raw in ws:
                try:
                    data = json.loads(raw)
                except Exception:
                    continue
                msg = data.get("msg") or {}
                if msg.get("status") != "settled":
                    continue
                ticker = msg.get("market_ticker")
                if not ticker:
                    continue
                yield SettlementEvent(
                    platform="kalshi",
                    external_id=ticker,
                    settlement_value=_settlement_value_from(msg),
                    settled_at=datetime.now(timezone.utc),
                )

    async def fetch_status(self, external_id: str) -> Optional[SettlementEvent]:  # pragma: no cover - network
        import httpx
        url = "https://trading-api.kalshi.com/trade-api/v2/markets/" + external_id
        async with httpx.AsyncClient() as client:
            resp = await client.get(url)
            if resp.status_code != 200:
                return None
            data = resp.json().get("market", {})
            if data.get("status") != "settled":
                return None
            return SettlementEvent(
                platform="kalshi",
                external_id=external_id,
                settlement_value=_settlement_value_from(data),
                settled_at=datetime.now(timezone.utc),
            )


def _settlement_value_from(msg: dict) -> float:
    if "settlement_value" in msg:
        return float(msg["settlement_value"])
    result = msg.get("result")
    if result == "yes":
        return 1.0
    if result == "no":
        return 0.0
    return 0.0


# --- run loops ----------------------------------------------------------- #

async def run_ws_subscriber(source: SettlementSource, handler: SettlementHandler) -> None:
    async for event in source.stream_settlements():
        try:
            await handler.apply(event)
        except Exception:
            logger.exception("settlement handler failed for %s", event.external_id)


async def run_poll_fallback(
    source: SettlementSource,
    handler: SettlementHandler,
    session_factory,
    interval_seconds: int = config.SETTLEMENT_FALLBACK_POLL_INTERVAL_SECONDS,
) -> None:
    """Sweep open positions every `interval_seconds`, polling each unique
    market for status. Catches anything the WS missed.
    """
    while True:
        try:
            await poll_once(source, handler, session_factory)
        except Exception:
            logger.exception("settlement poll fallback failed")
        await asyncio.sleep(interval_seconds)


async def poll_once(
    source: SettlementSource,
    handler: SettlementHandler,
    session_factory,
) -> int:
    """Single sweep — exposed separately so tests don't need a sleep loop."""
    async with session_factory() as session:
        stmt = (
            select(Market)
            .join(Position, Position.market_id == Market.id)
            .where(Market.platform == "kalshi", Position.status == "open")
            .distinct()
        )
        result = await session.execute(stmt)
        markets = list(result.scalars().all())

    settled = 0
    for market in markets:
        event = await source.fetch_status(market.external_id)
        if event is None:
            continue
        settled += await handler.apply(event)
    return settled
