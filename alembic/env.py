"""Alembic migration environment.

Imports all models so autogenerate sees the full metadata. Targets sync URL —
async drivers are converted to their sync equivalent for migration runs only;
the application itself uses the async engine in `sigil.db`.
"""
from __future__ import annotations

import os
import sys
from logging.config import fileConfig
from pathlib import Path

from alembic import context
from sqlalchemy import engine_from_config, pool

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from sigil.db import Base  # noqa: E402
from sigil import models  # noqa: F401,E402  (registers tables on Base.metadata)
from sigil.config import config as sigil_config  # noqa: E402

cfg = context.config

if cfg.config_file_name is not None:
    fileConfig(cfg.config_file_name)


def _resolve_sync_url() -> str:
    url = os.environ.get("ALEMBIC_DATABASE_URL") or sigil_config.DATABASE_URL
    # alembic runs sync; map async driver names to their sync equivalents
    if url.startswith("postgresql+asyncpg://"):
        url = url.replace("postgresql+asyncpg://", "postgresql+psycopg://", 1)
    if url.startswith("sqlite+aiosqlite://"):
        url = url.replace("sqlite+aiosqlite://", "sqlite://", 1)
    return url


cfg.set_main_option("sqlalchemy.url", _resolve_sync_url())

target_metadata = Base.metadata


def run_migrations_offline() -> None:
    url = cfg.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    connectable = engine_from_config(
        cfg.get_section(cfg.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            compare_type=True,
        )
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
