"""Shared pytest fixtures.

In-memory SQLite per test for isolation. Sigil modules are imported lazily
inside fixtures so that an import failure in (e.g.) `sigil.ingestion.runner`
doesn't break collection of unrelated test directories. SQLite check_same_thread
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


@pytest.fixture(scope="session")
def event_loop():
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


@pytest_asyncio.fixture
async def engine():
    from sigil.db import Base
    import sigil.models  # noqa: F401  (registers tables on Base.metadata)

    eng = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False, future=True)
    async with eng.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield eng
    await eng.dispose()


@pytest_asyncio.fixture
async def session_factory(engine):
    import sigil.db as sigil_db

    factory = async_sessionmaker(bind=engine, class_=AsyncSession, expire_on_commit=False)

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
    # Lazy imports: a syntax error in either module should not block collection
    # of test directories that don't touch reconciliation / ingestion runner.
    try:
        from sigil.execution import reconciliation as recon
    except Exception:
        recon = None
    try:
        from sigil.ingestion import runner as runner_module
    except Exception:
        runner_module = None

    if recon is not None:
        recon.reset_freeze_state()
    if runner_module is not None:
        runner_module.reset_source_state()
    yield
    if recon is not None:
        recon.reset_freeze_state()
    if runner_module is not None:
        runner_module.reset_source_state()


@pytest_asyncio.fixture
async def sample_market(session):
    import sigil.models as models

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
async def sample_bankroll(session):
    import sigil.models as models

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
async def sample_position(session, sample_market):
    import sigil.models as models

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
