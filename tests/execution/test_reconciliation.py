"""Reconciliation hysteresis (REVIEW-DECISIONS 1D).

The hysteresis counter tracks how many CONSECUTIVE exchange reports agree
with each other. We don't trust a one-off exchange reading that disagrees
with local — we wait until the exchange has reported the same value
`config.RECONCILIATION_HYSTERESIS_MATCHES` times in a row before letting
exchange-state-overrides-local. While exchange and local disagree (whether
the exchange is flapping or just stably wrong from local's view), new orders
on that market are frozen.
"""
from __future__ import annotations

from uuid import uuid4

import pytest
from sqlalchemy import select

from sigil.config import config
from sigil.execution.reconciliation import (
    ExchangePosition,
    ReconciliationTracker,
    is_frozen,
)
from sigil.models import Position, ReconciliationObservation


@pytest.mark.critical
async def test_phantom_zero_does_not_overwrite_local_below_hysteresis(session, sample_market, sample_position):
    """1D phantom-position scenario: exchange briefly reports 0 while local
    has 50. After a single observation we must NOT have wiped local."""
    tracker = ReconciliationTracker(session)
    exchange = ExchangePosition(
        platform="kalshi",
        market_id=sample_market.id,
        outcome="yes",
        quantity=0,
    )
    outcome = await tracker.observe(exchange)
    await session.commit()

    assert outcome.is_match is False
    assert outcome.overrode_local is False
    assert outcome.frozen is True
    assert is_frozen("kalshi", sample_market.id, "yes")

    refreshed = await session.get(Position, sample_position.id)
    assert refreshed.quantity == 50
    assert refreshed.status == "open"


@pytest.mark.critical
async def test_phantom_clears_when_exchange_recovers(session, sample_market, sample_position):
    tracker = ReconciliationTracker(session)
    phantom = ExchangePosition("kalshi", sample_market.id, "yes", 0)
    matching = ExchangePosition("kalshi", sample_market.id, "yes", 50)

    await tracker.observe(phantom); await session.commit()
    assert is_frozen("kalshi", sample_market.id, "yes")

    out = await tracker.observe(matching); await session.commit()
    # exchange flipped value -> consec resets to 1, but local==exchange now
    assert out.is_match is True
    assert is_frozen("kalshi", sample_market.id, "yes") is False


@pytest.mark.critical
async def test_three_consecutive_consistent_exchange_observations_apply_override(
    session, sample_market, sample_position
):
    """Exchange reports 30 three times in a row while local has 50. After the
    third consistent reading we trust exchange and overwrite local to 30."""
    tracker = ReconciliationTracker(session)
    exchange = ExchangePosition("kalshi", sample_market.id, "yes", 30)
    last = None
    for _ in range(config.RECONCILIATION_HYSTERESIS_MATCHES):
        last = await tracker.observe(exchange)
        await session.commit()
    assert last.consecutive_matches >= config.RECONCILIATION_HYSTERESIS_MATCHES
    assert last.overrode_local is True
    assert is_frozen("kalshi", sample_market.id, "yes") is False

    refreshed = await session.get(Position, sample_position.id)
    assert refreshed.quantity == 30


@pytest.mark.critical
async def test_flapping_exchange_resets_counter(session, sample_market, sample_position):
    tracker = ReconciliationTracker(session)
    a = ExchangePosition("kalshi", sample_market.id, "yes", 0)
    b = ExchangePosition("kalshi", sample_market.id, "yes", 25)

    await tracker.observe(a); await session.commit()
    await tracker.observe(a); await session.commit()
    out = await tracker.observe(b); await session.commit()
    # Exchange flipped: counter reset to 1.
    assert out.consecutive_matches == 1
    assert is_frozen("kalshi", sample_market.id, "yes") is True


@pytest.mark.critical
async def test_observations_persist_to_table(session, sample_market, sample_position):
    tracker = ReconciliationTracker(session)
    exchange = ExchangePosition("kalshi", sample_market.id, "yes", 0)  # mismatch vs local 50
    await tracker.observe(exchange)
    await session.commit()
    rows = (await session.execute(select(ReconciliationObservation))).scalars().all()
    assert len(rows) == 1
    assert rows[0].is_match is False
    assert rows[0].exchange_qty == 0
    assert rows[0].local_qty == 50


async def test_override_creates_position_when_local_missing(session, sample_market):
    tracker = ReconciliationTracker(session)
    exchange = ExchangePosition("kalshi", sample_market.id, "yes", 25)
    for _ in range(config.RECONCILIATION_HYSTERESIS_MATCHES):
        await tracker.observe(exchange)
        await session.commit()
    pos = (await session.execute(
        select(Position).where(Position.market_id == sample_market.id, Position.outcome == "yes")
    )).scalar_one()
    assert pos.quantity == 25
    assert pos.status == "open"


async def test_matching_state_no_op_override_does_not_change_position(session, sample_market, sample_position):
    """When exchange already agrees with local, override is a no-op rewrite."""
    tracker = ReconciliationTracker(session)
    exchange = ExchangePosition("kalshi", sample_market.id, "yes", 50)
    for _ in range(config.RECONCILIATION_HYSTERESIS_MATCHES):
        out = await tracker.observe(exchange)
        await session.commit()
    assert out.overrode_local is True
    refreshed = await session.get(Position, sample_position.id)
    assert refreshed.quantity == 50
