"""Shared fixtures for API tests.

Spins up an in-memory SQLite engine, builds the schema, and overrides the
`get_db` dependency so each test gets a fresh isolated DB session.
"""

from __future__ import annotations

import asyncio
from typing import AsyncIterator

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from sigil.api import routes as routes_module
from sigil.api.server import app
from sigil.db import Base, get_db


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
async def db_session(session_factory) -> AsyncIterator[AsyncSession]:
    async with session_factory() as session:
        yield session


@pytest.fixture
def client(session_factory, monkeypatch):
    """FastAPI TestClient bound to the in-memory DB and with the arb cache reset."""
    from fastapi.testclient import TestClient

    async def _override_get_db() -> AsyncIterator[AsyncSession]:
        async with session_factory() as session:
            yield session

    app.dependency_overrides[get_db] = _override_get_db
    routes_module._arb_cache["ts"] = 0.0
    routes_module._arb_cache["data"] = []
    try:
        with TestClient(app) as c:
            yield c
    finally:
        app.dependency_overrides.pop(get_db, None)
