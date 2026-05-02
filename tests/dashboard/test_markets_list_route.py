"""Markets-list view builder — query-param filtering + pagination.

We test the context builder (pure async, no HTTP), mirroring the
pattern in test_market_detail.py — Windows asyncio's proactor transport
is flaky in full-suite TestClient runs, so we exercise the same logic
deterministically against the in-memory SQLite session.
"""
from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

import pytest

from sigil.dashboard.views.markets_list import build_context
from sigil.models import Market, MarketPrice


async def _seed_market(
    session,
    *,
    ext_id: str,
    platform: str = "kalshi",
    title: str | None = None,
    taxonomy: str = "general",
    status: str = "open",
    archived: bool = False,
    last_price: float | None = 0.50,
    volume: float | None = 1000.0,
) -> Market:
    market = Market(
        id=uuid4(),
        platform=platform,
        external_id=ext_id,
        title=title or f"Will {ext_id} happen?",
        taxonomy_l1=taxonomy,
        market_type="binary",
        status=status,
        archived=archived,
    )
    session.add(market)
    if last_price is not None:
        session.add(MarketPrice(
            time=datetime.now(timezone.utc),
            market_id=market.id,
            bid=last_price - 0.01, ask=last_price + 0.01,
            last_price=last_price, volume_24h=volume, source="test",
        ))
    await session.commit()
    return market


async def test_default_view_all_hides_closed_and_gamma_archived(session):
    """Default view (``view=all``) shows only live markets. Both
    status!=open and the gamma archived flag count as 'no longer
    running'."""
    await _seed_market(session, ext_id="A-OPEN", status="open", archived=False)
    await _seed_market(session, ext_id="A-CLOSED", status="closed", archived=False)
    await _seed_market(session, ext_id="A-ARCH", status="open", archived=True)

    ctx = await build_context(session)
    ext_ids = {r.external_id for r in ctx.rows}
    assert "A-OPEN" in ext_ids
    assert "A-CLOSED" not in ext_ids       # non-open hidden by default
    assert "A-ARCH" not in ext_ids         # gamma archived hidden by default
    assert ctx.total == 1
    assert ctx.view == "all"


async def test_view_archived_inverts_to_non_running_only(session):
    """The archived tab surfaces non-running markets only — closed
    OR gamma-archived. Open + non-archived rows are hidden."""
    await _seed_market(session, ext_id="B-OPEN", status="open", archived=False)
    await _seed_market(session, ext_id="B-ARCH", status="open", archived=True)
    await _seed_market(session, ext_id="B-CLOSED", status="closed", archived=False)

    ctx = await build_context(session, view="archived")
    ext_ids = {r.external_id for r in ctx.rows}
    assert "B-ARCH" in ext_ids
    assert "B-CLOSED" in ext_ids
    assert "B-OPEN" not in ext_ids   # currently-running rows hidden in this tab
    assert ctx.view == "archived"
    assert ctx.total == 2


async def test_unknown_view_falls_back_to_all(session):
    await _seed_market(session, ext_id="V-OPEN", status="open", archived=False)
    await _seed_market(session, ext_id="V-CLOSED", status="closed", archived=False)

    ctx = await build_context(session, view="not-a-view")
    assert ctx.view == "all"
    assert {r.external_id for r in ctx.rows} == {"V-OPEN"}


async def test_view_spreads_falls_back_to_all_when_called_directly(session):
    """build_context isn't expected to handle view=spreads — the route
    intercepts that. Defensive fallback: if it's called anyway, treat
    it as 'all' rather than blowing up."""
    await _seed_market(session, ext_id="S-OPEN", status="open", archived=False)

    ctx = await build_context(session, view="spreads")
    assert ctx.view == "all"
    assert {r.external_id for r in ctx.rows} == {"S-OPEN"}


async def test_search_substring_case_insensitive(session):
    await _seed_market(session, ext_id="C1", title="Will Trump win Iowa?")
    await _seed_market(session, ext_id="C2", title="Will Biden run again?")
    await _seed_market(session, ext_id="C3", title="Eagles vs Chiefs SB winner")

    ctx = await build_context(session, q="trump")
    ext_ids = {r.external_id for r in ctx.rows}
    assert ext_ids == {"C1"}
    assert ctx.total == 1


async def test_platform_filter(session):
    await _seed_market(session, ext_id="D1", platform="kalshi")
    await _seed_market(session, ext_id="D2", platform="polymarket")
    await _seed_market(session, ext_id="D3", platform="polymarket")

    ctx = await build_context(session, platform="polymarket")
    ext_ids = {r.external_id for r in ctx.rows}
    assert ext_ids == {"D2", "D3"}


async def test_category_filter(session):
    await _seed_market(session, ext_id="E1", taxonomy="sports")
    await _seed_market(session, ext_id="E2", taxonomy="economics")
    await _seed_market(session, ext_id="E3", taxonomy="sports")

    ctx = await build_context(session, category="sports")
    ext_ids = {r.external_id for r in ctx.rows}
    assert ext_ids == {"E1", "E3"}


async def test_status_any_scopes_to_view(session):
    await _seed_market(session, ext_id="F-OPEN", status="open")
    await _seed_market(session, ext_id="F-CLOSED", status="closed")

    # status=any disables the per-view status filter, but the view
    # itself still scopes the result. "All" tab + status=any: only
    # non-archived rows that happen to be open (gamma archived flag
    # off + status==open is enforced when status filter is unset OR
    # =any — but we only enforce status==open when a status filter
    # isn't doing the work). The view branch above keeps things tight:
    # status=any on the "All" tab shows everything that isn't
    # gamma-archived, including closed.
    ctx_all = await build_context(session, status="any", view="all")
    # Both F-OPEN and F-CLOSED have archived=False → "All" + status=any
    # hides nothing.
    assert {r.external_id for r in ctx_all.rows} == {"F-OPEN", "F-CLOSED"}

    ctx_arch = await build_context(session, status="any", view="archived")
    # status=any on the archived tab disables the status≠open clause,
    # but the view still requires (status≠open OR archived=True). So
    # only F-CLOSED matches.
    assert {r.external_id for r in ctx_arch.rows} == {"F-CLOSED"}


async def test_explicit_status_closed_overrides_default(session):
    await _seed_market(session, ext_id="F2-OPEN", status="open")
    await _seed_market(session, ext_id="F2-CLOSED", status="closed")

    # Picking a status explicitly should surface those rows even on
    # the All tab (the user is asking for them by name).
    ctx = await build_context(session, status="closed")
    assert {r.external_id for r in ctx.rows} == {"F2-CLOSED"}


async def test_pagination_advances_offset(session):
    # Seed > 50 (the page size) to force pagination.
    for i in range(75):
        await _seed_market(
            session, ext_id=f"P{i:03d}", title=f"market {i:03d}",
        )

    page1 = await build_context(session)
    page2 = await build_context(session, page="2")
    assert page1.page == 1
    assert page2.page == 2
    assert len(page1.rows) == 50
    assert len(page2.rows) == 25
    assert page1.total_pages == 2
    assert page1.total == 75
    p1_ids = {r.external_id for r in page1.rows}
    p2_ids = {r.external_id for r in page2.rows}
    assert p1_ids.isdisjoint(p2_ids)


async def test_filter_options_lists_distinct_values(session):
    await _seed_market(session, ext_id="O1", platform="kalshi", taxonomy="sports", status="open")
    await _seed_market(session, ext_id="O2", platform="polymarket", taxonomy="economics", status="open")
    await _seed_market(session, ext_id="O3", platform="polymarket", taxonomy="economics", status="closed")

    ctx = await build_context(session)
    assert set(ctx.platforms) == {"kalshi", "polymarket"}
    assert set(ctx.categories) == {"sports", "economics"}
    assert "open" in ctx.statuses


async def test_invalid_page_param_falls_back_to_one(session):
    await _seed_market(session, ext_id="G1")
    ctx = await build_context(session, page="not-a-number")
    assert ctx.page == 1
