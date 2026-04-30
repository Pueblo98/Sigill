"""Shared pytest fixtures.

In-memory SQLite per test for isolation. We import `sigil.models` so that
`Base.metadata.create_all` builds the full schema. SQLite check_same_thread
is OK here — pytest-asyncio runs each test on a single event loop.
"""
from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from typing import AsyncIterator
from uuid import uuid4

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

import sigil.db as sigil_db
from sigil.db import Base
import sigil.models as models  # noqa: F401  (registers tables on Base.metadata)
from sigil.execution import reconciliation as recon
from sigil.ingestion import runner as runner_module


@pytest.fixture(scope="session")
def event_loop():
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


@pytest_asyncio.fixture
async def engine():
    eng = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False, future=True)
    async with eng.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield eng
    await eng.dispose()


@pytest_asyncio.fixture
async def session_factory(engine):
    factory = async_sessionmaker(bind=engine, class_=AsyncSession, expire_on_commit=False)

    # Re-bind sigil.db globals so app code that reaches for `AsyncSessionLocal`
    # / `get_session` lands on the in-memory schema for the duration of the test.
    saved_engine = sigil_db.engine
    saved_factory = sigil_db.AsyncSessionLocal
    sigil_db.engine = engine
    sigil_db.AsyncSessionLocal = factory
    try:
        yield factory
    finally:
        sigil_db.engine = saved_engine
        sigil_db.AsyncSessionLocal = saved_factory


@pytest_asyncio.fixture
async def session(session_factory) -> AsyncIterator[AsyncSession]:
    async with session_factory() as s:
        yield s


@pytest.fixture(autouse=True)
def _reset_global_state():
    recon.reset_freeze_state()
    runner_module.reset_source_state()
    yield
    recon.reset_freeze_state()
    runner_module.reset_source_state()


@pytest_asyncio.fixture
async def sample_market(session) -> models.Market:
    market = models.Market(
        id=uuid4(),
        platform="kalshi",
        external_id="KAL-TEST-001",
        title="Sample test market",
        taxonomy_l1="sports",
        market_type="binary",
        status="open",
    )
    session.add(market)
    await session.commit()
    return market


@pytest_asyncio.fixture
async def sample_bankroll(session) -> models.BankrollSnapshot:
    snap = models.BankrollSnapshot(
        time=datetime.now(timezone.utc),
        mode="paper",
        equity=5000.0,
        realized_pnl_total=0.0,
        unrealized_pnl_total=0.0,
        settled_trades_total=25,
        settled_trades_30d=10,
    )
    session.add(snap)
    await session.commit()
    return snap


@pytest_asyncio.fixture
async def sample_position(session, sample_market) -> models.Position:
    pos = models.Position(
        id=uuid4(),
        platform="kalshi",
        market_id=sample_market.id,
        mode="live",
        outcome="yes",
        quantity=50,
        avg_entry_price=0.42,
        status="open",
    )
    session.add(pos)
    await session.commit()
    return pos
