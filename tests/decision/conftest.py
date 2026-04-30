"""Shared fixtures for Lane B decision tests.

Provides an in-memory SQLite session bound to the locked schema, plus a few
factories that make BankrollSnapshot rows easy to author.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import AsyncIterator

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from sigil.db import Base
from sigil.models import BankrollSnapshot  # noqa: F401  (ensure mapper registration)


@pytest_asyncio.fixture
async def db_session() -> AsyncIterator[AsyncSession]:
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", future=True)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    session_factory = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)
    async with session_factory() as session:
        yield session
    await engine.dispose()


@pytest.fixture
def utcnow() -> datetime:
    return datetime.now(timezone.utc).replace(microsecond=0)


@pytest.fixture
def make_snapshot(utcnow):
    """Factory for BankrollSnapshot rows; defaults satisfy the 2F gate."""

    def _make(
        equity: float,
        *,
        offset_days: float = 0.0,
        mode: str = "paper",
        settled_total: int = 25,
        settled_30d: int = 10,
        time: datetime | None = None,
    ) -> BankrollSnapshot:
        ts = time if time is not None else utcnow - timedelta(days=offset_days)
        return BankrollSnapshot(
            time=ts,
            mode=mode,
            equity=equity,
            realized_pnl_total=0.0,
            unrealized_pnl_total=0.0,
            settled_trades_total=settled_total,
            settled_trades_30d=settled_30d,
        )

    return _make
