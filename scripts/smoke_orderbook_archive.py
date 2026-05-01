"""Smoke test for the per-market per-day orderbook archive (TODO-1).

Drives a fake Kalshi WS feed through ``StreamProcessor + OrderbookArchive``
against a temporary SQLite DB, then asserts files appear at the expected
paths with the expected line counts. Exits non-zero on first mismatch.

Usage:

    .venv/Scripts/python.exe scripts/smoke_orderbook_archive.py
"""
from __future__ import annotations

import asyncio
import json
import os
import shutil
import sys
import tempfile
from datetime import datetime, timedelta, timezone
from uuid import uuid4

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = os.path.join(ROOT, "src")
if SRC not in sys.path:
    sys.path.insert(0, SRC)

import sigil.db as sigil_db
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from sigil.db import Base
import sigil.models  # noqa: F401  (registers tables on Base.metadata)
from sigil.ingestion.orderbook_archive import OrderbookArchive
from sigil.ingestion.runner import StreamProcessor
from sigil.models import Market


def _ok(label: str) -> None:
    print(f"[ OK ] {label}")


def _fail(label: str, detail: str = "") -> None:
    print(f"[FAIL] {label}: {detail}")
    sys.exit(1)


async def main() -> None:
    tmp = tempfile.mkdtemp(prefix="sigil_archive_smoke_")
    db_url = f"sqlite+aiosqlite:///{tmp}/smoke.db"
    archive_dir = os.path.join(tmp, "archive")
    print(f"--- orderbook archive smoke (tmp={tmp}) ---")

    engine = create_async_engine(db_url, echo=False, future=True)
    factory = async_sessionmaker(bind=engine, expire_on_commit=False)
    sigil_db.engine = engine
    sigil_db.AsyncSessionLocal = factory
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async with factory() as session:
        for ext in ("MKT-A", "MKT-B"):
            session.add(Market(
                id=uuid4(),
                platform="kalshi",
                external_id=ext,
                title=ext,
                taxonomy_l1="general",
                market_type="binary",
                status="open",
            ))
        await session.commit()
    _ok("seeded 2 markets in scratch DB")

    archive = OrderbookArchive(archive_dir, max_open_handles=8)
    processor = StreamProcessor(
        "Kalshi", "kalshi",
        os.path.join(tmp, "ticks.jsonl"),
        archive=archive,
    )

    now = datetime.now(timezone.utc)
    processor.batch = [
        {"market_id": "MKT-A", "platform": "kalshi", "time": now,
         "bid": 0.40, "ask": 0.50, "last_price": 0.45,
         "bids": [[40, 100]], "asks": [[50, 200]], "source": "exchange_ws"},
        {"market_id": "MKT-A", "platform": "kalshi",
         "time": now + timedelta(microseconds=1),
         "bid": 0.41, "ask": 0.51, "last_price": 0.46,
         "bids": [[41, 100]], "asks": [[51, 200]], "source": "exchange_ws"},
        {"market_id": "MKT-B", "platform": "kalshi", "time": now,
         "bid": 0.60, "ask": 0.70, "last_price": 0.65,
         "bids": [[60, 50]], "asks": [[70, 80]], "source": "exchange_ws"},
    ]
    inserted = await processor._flush_once()
    if inserted != 3:
        _fail("inserted MarketPrice rows", f"expected 3, got {inserted}")
    _ok(f"_flush_once() persisted {inserted} MarketPrice rows")
    archive.close()

    today = now.strftime("%Y-%m-%d")
    a_path = os.path.join(archive_dir, "kalshi", "MKT-A", f"{today}.jsonl")
    b_path = os.path.join(archive_dir, "kalshi", "MKT-B", f"{today}.jsonl")
    if not os.path.exists(a_path):
        _fail("MKT-A archive file missing", a_path)
    if not os.path.exists(b_path):
        _fail("MKT-B archive file missing", b_path)
    with open(a_path, encoding="utf-8") as f:
        a_lines = f.read().splitlines()
    with open(b_path, encoding="utf-8") as f:
        b_lines = f.read().splitlines()
    if len(a_lines) != 2:
        _fail("MKT-A line count", f"expected 2, got {len(a_lines)}")
    if len(b_lines) != 1:
        _fail("MKT-B line count", f"expected 1, got {len(b_lines)}")
    _ok(f"MKT-A archived 2 ticks, MKT-B archived 1 tick at {today}.jsonl")

    rec_a = json.loads(a_lines[0])
    if rec_a.get("external_id") != "MKT-A":
        _fail("external_id round-trip", str(rec_a))
    if rec_a.get("bids") != [[40, 100]] or rec_a.get("asks") != [[50, 200]]:
        _fail("depth round-trip", str(rec_a))
    if "market_id" in rec_a:
        _fail("market_id should be renamed to external_id", str(rec_a))
    _ok("JSONL records round-trip with depth + renamed external_id")

    await engine.dispose()
    shutil.rmtree(tmp, ignore_errors=True)
    print("\n[ OK ] all orderbook archive smoke assertions passed")


if __name__ == "__main__":
    asyncio.run(main())
