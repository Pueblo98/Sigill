"""Spin up uvicorn against the smoke DB for an end-to-end smoke check.

`Config` is a plain pydantic `BaseModel` and doesn't read env vars on its
own. We mutate `config` directly before importing the app so the lifespan
hook picks up our overrides instead of the defaults.

Usage:

    SIGIL_SMOKE_DB=./sigil_smoke.db SIGIL_SMOKE_PORT=8765 \
        .venv/Scripts/python.exe scripts/smoke_uvicorn.py
"""
from __future__ import annotations

import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = os.path.join(ROOT, "src")
if SRC not in sys.path:
    sys.path.insert(0, SRC)

db_path = os.environ.get("SIGIL_SMOKE_DB", "./sigil_smoke.db")
port = int(os.environ.get("SIGIL_SMOKE_PORT", "8765"))

from sigil.config import config  # noqa: E402

config.DATABASE_URL = f"sqlite+aiosqlite:///{db_path}"
config.DASHBOARD_ENABLED = True
config.API_BIND_HOST = "127.0.0.1"
config.API_BIND_PORT = port

import sigil.db as sigil_db  # noqa: E402

sigil_db.engine = sigil_db.create_async_engine(config.DATABASE_URL, echo=False)
sigil_db.AsyncSessionLocal = sigil_db.async_sessionmaker(
    bind=sigil_db.engine, expire_on_commit=False
)

import uvicorn  # noqa: E402


if __name__ == "__main__":
    uvicorn.run(
        "sigil.api.server:app",
        host="127.0.0.1",
        port=port,
        log_level="warning",
    )
