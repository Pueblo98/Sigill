"""Database engine + session management.

Schema is owned by alembic — do NOT call `Base.metadata.create_all` from here in
production code paths. The fallback to SQLite is preserved for local dev only;
fresh dev DBs come up via `alembic upgrade head` (or `init_db(create_all=True)`
exclusively for in-memory test fixtures).
"""
from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from typing import AsyncIterator

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase

from sigil.config import config

logger = logging.getLogger(__name__)

FALLBACK_URL = "sqlite+aiosqlite:///./sigil_dev.db"


class Base(DeclarativeBase):
    pass


engine = create_async_engine(config.DATABASE_URL, echo=False)
AsyncSessionLocal = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


def _rebind(url: str) -> None:
    global engine, AsyncSessionLocal
    engine = create_async_engine(url, echo=False)
    AsyncSessionLocal = async_sessionmaker(
        bind=engine,
        class_=AsyncSession,
        expire_on_commit=False,
    )


async def init_db(create_all: bool = False) -> None:
    """Verify the configured database is reachable.

    Falls back to a local SQLite file when the primary URL is unreachable,
    which is convenient for offline dev. Production callers should rely on
    alembic migrations to manage schema; `create_all=True` exists only so
    pytest fixtures can stand up an in-memory schema without alembic.
    """
    global engine
    try:
        async with engine.begin():
            pass
        logger.info("Connected to %s", config.DATABASE_URL.split("@")[-1])
    except Exception as exc:  # pragma: no cover - environmental
        logger.warning("Primary DB unreachable (%s); falling back to %s", exc, FALLBACK_URL)
        _rebind(FALLBACK_URL)

    if create_all:
        # Test/dev only — production schema is alembic-managed.
        from sigil import models  # noqa: F401  (registers tables)

        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)


@asynccontextmanager
async def get_session() -> AsyncIterator[AsyncSession]:
    """Async context manager yielding a session that auto-commits on exit
    and rolls back on exception. Prefer this over manually opening
    `AsyncSessionLocal()` so transaction boundaries stay predictable.
    """
    session = AsyncSessionLocal()
    try:
        yield session
        await session.commit()
    except Exception:
        await session.rollback()
        raise
    finally:
        await session.close()


async def get_db() -> AsyncIterator[AsyncSession]:
    """FastAPI dependency: yields a session without auto-commit."""
    async with AsyncSessionLocal() as session:
        yield session
