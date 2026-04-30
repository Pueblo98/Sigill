"""Shared fixtures for dashboard tests.

Provides an in-memory SQLite session + sample-row helpers. Mirrors the
patterns in tests/api/conftest.py — we don't share that fixture file because
F1 widgets shouldn't depend on the FastAPI app being importable.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import AsyncIterator, Callable
from uuid import uuid4

import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from sigil.db import Base
from sigil.models import Market


@pytest_asyncio.fixture
async def db_engine():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    try:
        yield engine
    finally:
        await engine.dispose()


@pytest_asyncio.fixture
async def session_factory(db_engine):
    return async_sessionmaker(bind=db_engine, class_=AsyncSession, expire_on_commit=False)


@pytest_asyncio.fixture
async def session(session_factory) -> AsyncIterator[AsyncSession]:
    async with session_factory() as s:
        yield s


@pytest_asyncio.fixture
async def sample_market(session: AsyncSession) -> Market:
    m = Market(
        platform="kalshi",
        external_id=f"TEST-{uuid4().hex[:6]}",
        title="Will it rain?",
        taxonomy_l1="weather",
        status="open",
    )
    session.add(m)
    await session.commit()
    await session.refresh(m)
    return m
