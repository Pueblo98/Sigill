"""Execution log view builder — query-param filtering + pagination.

Mirrors :mod:`tests.dashboard.test_markets_list_route`: exercises the
``build_context`` async function directly on an in-memory SQLite session.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from uuid import uuid4

import pytest

from sigil.dashboard.views.execution_log import build_context
from sigil.models import Market, Order


async def _seed_market(session, *, ext_id: str = "KX-EXEC", platform: str = "kalshi") -> Market:
    market = Market(
        id=uuid4(),
        platform=platform,
        external_id=ext_id,
        title=f"Will {ext_id}?",
        taxonomy_l1="sports",
        market_type="binary",
        status="open",
    )
    session.add(market)
    await session.commit()
    await session.refresh(market)
    return market


async def _seed_order(
    session,
    *,
    market: Market,
    platform: str = "kalshi",
    mode: str = "paper",
    side: str = "buy",
    outcome: str = "yes",
    status: str = "filled",
    quantity: int = 10,
    filled_quantity: int = 10,
    price: float = 0.50,
    avg_fill_price: float | None = 0.50,
    created_at: datetime | None = None,
) -> Order:
    order = Order(
        id=uuid4(),
        platform=platform,
        market_id=market.id,
        client_order_id=f"co-{uuid4().hex[:6]}",
        external_order_id=f"ex-{uuid4().hex[:6]}",
        mode=mode,
        side=side,
        outcome=outcome,
        order_type="limit",
        price=price,
        quantity=quantity,
        filled_quantity=filled_quantity,
        avg_fill_price=avg_fill_price,
        fees=0.0,
        status=status,
    )
    if created_at is not None:
        order.created_at = created_at
    session.add(order)
    await session.commit()
    return order


async def test_empty_db_returns_zero_total(session):
    ctx = await build_context(session)
    assert ctx.total == 0
    assert ctx.rows == []
    assert ctx.page == 1
    assert ctx.total_pages == 1


async def test_default_returns_all_orders_newest_first(session):
    market = await _seed_market(session)
    older = datetime.now(timezone.utc) - timedelta(hours=2)
    newer = datetime.now(timezone.utc)
    await _seed_order(session, market=market, status="filled", created_at=older)
    await _seed_order(session, market=market, status="created", created_at=newer)

    ctx = await build_context(session)
    assert ctx.total == 2
    assert len(ctx.rows) == 2
    # Newest first.
    assert ctx.rows[0].status == "created"
    assert ctx.rows[1].status == "filled"
    # Market metadata resolved.
    assert ctx.rows[0].market_external_id == "KX-EXEC"
    assert ctx.rows[0].market_title.startswith("Will KX-EXEC")


async def test_platform_filter(session):
    kx = await _seed_market(session, ext_id="KX-A", platform="kalshi")
    pm = await _seed_market(session, ext_id="PM-A", platform="polymarket")
    await _seed_order(session, market=kx, platform="kalshi")
    await _seed_order(session, market=pm, platform="polymarket")
    await _seed_order(session, market=pm, platform="polymarket")

    ctx = await build_context(session, platform="polymarket")
    assert ctx.total == 2
    assert all(r.platform == "polymarket" for r in ctx.rows)


async def test_mode_filter(session):
    market = await _seed_market(session)
    await _seed_order(session, market=market, mode="paper")
    await _seed_order(session, market=market, mode="paper")
    await _seed_order(session, market=market, mode="live")

    ctx_paper = await build_context(session, mode="paper")
    assert ctx_paper.total == 2
    assert all(r.mode == "paper" for r in ctx_paper.rows)

    ctx_live = await build_context(session, mode="live")
    assert ctx_live.total == 1
    assert ctx_live.rows[0].mode == "live"


async def test_status_filter(session):
    market = await _seed_market(session)
    await _seed_order(session, market=market, status="filled")
    await _seed_order(session, market=market, status="cancelled")
    await _seed_order(session, market=market, status="filled")

    ctx = await build_context(session, status="filled")
    assert ctx.total == 2
    assert all(r.status == "filled" for r in ctx.rows)


async def test_combined_filters(session):
    kx = await _seed_market(session, ext_id="KX-COMBO", platform="kalshi")
    pm = await _seed_market(session, ext_id="PM-COMBO", platform="polymarket")
    await _seed_order(session, market=kx, platform="kalshi", mode="paper", status="filled")
    await _seed_order(session, market=kx, platform="kalshi", mode="live", status="filled")
    await _seed_order(session, market=pm, platform="polymarket", mode="paper", status="filled")
    await _seed_order(session, market=kx, platform="kalshi", mode="paper", status="cancelled")

    ctx = await build_context(
        session, platform="kalshi", mode="paper", status="filled"
    )
    assert ctx.total == 1
    assert ctx.rows[0].platform == "kalshi"
    assert ctx.rows[0].mode == "paper"
    assert ctx.rows[0].status == "filled"


async def test_pagination(session):
    market = await _seed_market(session)
    # Seed > 50 (the page size) to force pagination.
    base = datetime.now(timezone.utc)
    for i in range(75):
        await _seed_order(
            session, market=market,
            created_at=base - timedelta(seconds=i),
        )

    p1 = await build_context(session)
    p2 = await build_context(session, page="2")
    assert p1.page == 1
    assert p2.page == 2
    assert len(p1.rows) == 50
    assert len(p2.rows) == 25
    assert p1.total_pages == 2
    assert p1.total == 75
    p1_ids = {r.id for r in p1.rows}
    p2_ids = {r.id for r in p2.rows}
    assert p1_ids.isdisjoint(p2_ids)


async def test_invalid_page_param_falls_back_to_one(session):
    market = await _seed_market(session)
    await _seed_order(session, market=market)
    ctx = await build_context(session, page="not-a-number")
    assert ctx.page == 1


async def test_filter_options_lists_distinct_values(session):
    kx = await _seed_market(session, ext_id="KX-OPTS", platform="kalshi")
    pm = await _seed_market(session, ext_id="PM-OPTS", platform="polymarket")
    await _seed_order(session, market=kx, platform="kalshi", mode="paper", status="filled")
    await _seed_order(session, market=pm, platform="polymarket", mode="live", status="created")

    ctx = await build_context(session)
    assert set(ctx.platforms) == {"kalshi", "polymarket"}
    assert set(ctx.modes) == {"paper", "live"}
    assert {"filled", "created"}.issubset(set(ctx.statuses))
