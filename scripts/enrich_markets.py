"""One-shot backfill: fill `description`, `archived`, and real `taxonomy_l1`
on existing Market rows.

Idempotent — only writes a column when its current value is NULL/'general'
so re-running is safe. Designed to run after the
``a4b1c2d3e4f5_add_market_description_archived`` migration, against the
~258 markets already populated by ingestion.

Per platform:

- **polymarket**: hits Polymarket gamma `/markets?condition_ids=<cid>`
  per market, pulls ``description`` + ``archived``. Free, no auth.
- **kalshi**: re-derives ``taxonomy_l1`` from the ticker prefix using
  the same map ``sigil.ingestion.kalshi`` uses at ingest time. Description
  stays NULL until Kalshi auth lands.

Logs progress per platform; commits in batches of 50. Run with::

    .venv/Scripts/python.exe scripts/enrich_markets.py
"""
from __future__ import annotations

import asyncio
import logging
import os
import sys
from typing import Optional

import httpx

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = os.path.join(ROOT, "src")
if SRC not in sys.path:
    sys.path.insert(0, SRC)

from sqlalchemy import select

from sigil.db import AsyncSessionLocal
from sigil.ingestion.kalshi import _infer_category_from_ticker
from sigil.models import Market
from sigil.secrets import load_and_inject


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
)
log = logging.getLogger("enrich_markets")


_GAMMA_BASE = "https://gamma-api.polymarket.com"
_BATCH_SIZE = 50


async def _fetch_polymarket_detail(
    client: httpx.AsyncClient, condition_id: str
) -> Optional[dict]:
    """One gamma row by conditionId. Returns ``None`` on miss / non-200."""
    try:
        r = await client.get(
            "/markets",
            params={"condition_ids": condition_id, "limit": "1"},
        )
    except Exception as exc:  # noqa: BLE001
        log.warning("gamma fetch %s failed: %s", condition_id, exc)
        return None
    if r.status_code != 200:
        return None
    body = r.json()
    if not isinstance(body, list) or not body:
        return None
    return body[0]


async def _enrich_polymarket(session) -> tuple[int, int]:
    rows = (
        await session.execute(
            select(Market).where(Market.platform == "polymarket")
        )
    ).scalars().all()
    log.info("polymarket: %d markets to inspect", len(rows))

    n_desc = 0
    n_arch = 0
    async with httpx.AsyncClient(base_url=_GAMMA_BASE, timeout=20.0) as client:
        for i, market in enumerate(rows, 1):
            need_desc = market.description is None
            # Always re-mirror archived (cheap) so flips propagate.
            detail = await _fetch_polymarket_detail(client, market.external_id)
            if detail is None:
                continue
            if need_desc:
                desc = detail.get("description")
                if isinstance(desc, str) and desc.strip():
                    market.description = desc.strip()
                    n_desc += 1
            archived_raw = detail.get("archived")
            if archived_raw is not None:
                archived = bool(archived_raw)
                if archived != market.archived:
                    market.archived = archived
                    n_arch += 1
            if i % _BATCH_SIZE == 0:
                await session.commit()
                log.info("polymarket: committed %d/%d", i, len(rows))
    await session.commit()
    return n_desc, n_arch


async def _enrich_kalshi(session) -> int:
    rows = (
        await session.execute(
            select(Market).where(Market.platform == "kalshi")
        )
    ).scalars().all()
    log.info("kalshi: %d markets to inspect", len(rows))

    n = 0
    for i, market in enumerate(rows, 1):
        if (market.taxonomy_l1 or "general") != "general":
            continue
        # Use the external_id as ticker; we don't store event_ticker.
        derived = _infer_category_from_ticker(None, market.external_id)
        if derived != "general":
            market.taxonomy_l1 = derived
            n += 1
        if i % _BATCH_SIZE == 0:
            await session.commit()
            log.info("kalshi: committed %d/%d", i, len(rows))
    await session.commit()
    return n


async def main() -> int:
    load_and_inject()
    async with AsyncSessionLocal() as session:
        desc, arch = await _enrich_polymarket(session)
        log.info("polymarket: filled description for %d, archived for %d", desc, arch)
        cats = await _enrich_kalshi(session)
        log.info("kalshi: re-categorized %d markets via ticker prefix", cats)
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
