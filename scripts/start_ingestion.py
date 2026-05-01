"""Start the live ingestion + sync stack as a single foreground process.

The FastAPI dashboard server (`python -m sigil.api.server`) is the
*read* path; ingestion is a separate concern. This script spins up
both ingestion entrypoints concurrently:

- ``sigil.main.main_loop`` — Kalshi REST market sync every ~60s plus
  the bankroll snapshot APScheduler job. Optionally the settlement
  WS subscriber if ``SETTLEMENT_WS_ENABLED=true``.
- ``sigil.ingestion.runner.run_ingestion`` — Kalshi + Polymarket
  WebSocket price streams, batched into the JSONL lake and the
  ``MarketPrice`` table. Honors ``ORDERBOOK_ARCHIVE_ENABLED``.

Ctrl+C tears both down cleanly.

Pre-flight: live Kalshi requires ``config.KALSHI_KEY_ID`` +
``KALSHI_PRIVATE_KEY_PATH`` (or ``_PEM``). Without those the Kalshi
adapter logs a warning and returns an empty market list — Polymarket
still flows.

Usage:

    .venv/Scripts/python.exe scripts/start_ingestion.py
"""
from __future__ import annotations

import asyncio
import logging
import os
import signal
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = os.path.join(ROOT, "src")
if SRC not in sys.path:
    sys.path.insert(0, SRC)

from sigil.config import config
from sigil.ingestion.runner import run_ingestion
from sigil.main import main_loop

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
log = logging.getLogger("sigil.start_ingestion")


def _preflight() -> None:
    print("--- Sigil ingestion bootstrap ---")
    print(f"  DATABASE_URL                  {config.DATABASE_URL}")
    print(f"  ORDERBOOK_ARCHIVE_ENABLED     {config.ORDERBOOK_ARCHIVE_ENABLED}")
    print(f"  SETTLEMENT_WS_ENABLED         {config.SETTLEMENT_WS_ENABLED}")
    have_kid = bool(config.KALSHI_KEY_ID)
    have_key = bool(config.KALSHI_PRIVATE_KEY_PEM or config.KALSHI_PRIVATE_KEY_PATH)
    print(f"  Kalshi auth (KEY_ID + key)    {'configured' if (have_kid and have_key) else 'MISSING — Kalshi will be skipped'}")
    print()


async def main() -> int:
    _preflight()

    # Both coroutines run forever; gather propagates the first exception.
    main_task = asyncio.create_task(main_loop(), name="sigil.main_loop")
    ingest_task = asyncio.create_task(run_ingestion(), name="sigil.run_ingestion")

    done, pending = await asyncio.wait(
        {main_task, ingest_task},
        return_when=asyncio.FIRST_EXCEPTION,
    )

    rc = 0
    for t in done:
        if t.cancelled():
            continue
        exc = t.exception()
        if exc is not None:
            log.error("task %s exited: %r", t.get_name(), exc)
            rc = 1

    for t in pending:
        t.cancel()
    if pending:
        await asyncio.gather(*pending, return_exceptions=True)
    return rc


def _install_signal_handlers(loop: asyncio.AbstractEventLoop) -> None:
    """Best-effort SIGINT/SIGTERM handler — Windows doesn't support
    add_signal_handler, so we just rely on KeyboardInterrupt there."""
    try:
        for sig in (signal.SIGINT, signal.SIGTERM):
            loop.add_signal_handler(sig, lambda: [t.cancel() for t in asyncio.all_tasks(loop)])
    except NotImplementedError:
        pass  # Windows


if __name__ == "__main__":
    try:
        rc = asyncio.run(main())
    except KeyboardInterrupt:
        rc = 130
    sys.exit(rc)
