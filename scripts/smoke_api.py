"""W2.4 in-process API smoke.

Boots the FastAPI app via TestClient (no port binding) against the smoke DB
and hits every read endpoint. Asserts shape, not specific data.
"""
from __future__ import annotations

import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = os.path.join(ROOT, "src")
if SRC not in sys.path:
    sys.path.insert(0, SRC)

# Point the app at the smoke DB. `Config` is a plain pydantic BaseModel and
# doesn't read env vars on its own, so we mutate it directly before any other
# code (including the FastAPI lifespan) reads `config.DATABASE_URL`.
db_path = os.environ.get("SIGIL_SMOKE_DB", "./sigil_smoke.db")
db_url = f"sqlite+aiosqlite:///{db_path}"

from sigil.config import config  # noqa: E402

config.DATABASE_URL = db_url

import sigil.db as sigil_db  # noqa: E402

sigil_db.engine = sigil_db.create_async_engine(config.DATABASE_URL, echo=False)
sigil_db.AsyncSessionLocal = sigil_db.async_sessionmaker(
    bind=sigil_db.engine, expire_on_commit=False
)

from fastapi.testclient import TestClient  # noqa: E402

from sigil.api.server import app  # noqa: E402


def _ok(label: str) -> None:
    print(f"[ OK ] {label}")


def _fail(label: str, detail: str) -> None:
    print(f"[FAIL] {label}: {detail}")
    sys.exit(1)


def main() -> None:
    print(f"--- Sigil API smoke (db={config.DATABASE_URL}) ---")
    with TestClient(app) as client:
        r = client.get("/api/health")
        if r.status_code != 200:
            _fail("/api/health", f"status={r.status_code}")
        body = r.json()
        if "state" not in body or "sources" not in body:
            _fail("/api/health shape", str(body)[:200])
        _ok(f"/api/health -> state={body['state']}, sources={len(body['sources'])}")

        r = client.get("/api/markets")
        if r.status_code != 200:
            _fail("/api/markets", f"status={r.status_code}")
        markets = r.json()
        if not isinstance(markets, list):
            _fail("/api/markets shape", "expected list")
        _ok(f"/api/markets -> {len(markets)} markets")

        r = client.get("/api/portfolio")
        if r.status_code != 200:
            _fail("/api/portfolio", f"status={r.status_code}")
        port = r.json()
        if "state" not in port or "balance" not in port:
            _fail("/api/portfolio shape", str(port)[:200])
        _ok(f"/api/portfolio -> state={port['state']}, balance={port['balance']}")

        r = client.get("/api/positions")
        if r.status_code != 200:
            _fail("/api/positions", f"status={r.status_code}")
        _ok(f"/api/positions -> {len(r.json())} rows")

        r = client.get("/api/orders")
        if r.status_code != 200:
            _fail("/api/orders", f"status={r.status_code}")
        _ok(f"/api/orders -> {len(r.json())} rows")

        r = client.get("/api/predictions")
        if r.status_code != 200:
            _fail("/api/predictions", f"status={r.status_code}")
        _ok(f"/api/predictions -> {len(r.json())} rows")

        if markets:
            ext_id = markets[0].get("external_id")
            r = client.get(f"/api/markets/{ext_id}")
            if r.status_code != 200:
                _fail(f"/api/markets/{ext_id}", f"status={r.status_code}")
            _ok(f"/api/markets/{{external_id}} -> {r.json().get('title')}")

        r = client.get("/api/markets/nonexistent-ticker")
        if r.status_code != 404:
            _fail("/api/markets/{unknown}", f"expected 404, got {r.status_code}")
        _ok("/api/markets/{unknown} -> 404 as expected")

    print("\n[ OK ] all API smoke assertions passed")


if __name__ == "__main__":
    main()
