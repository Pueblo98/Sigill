"""Markets list page — server-side filtered + paginated catalog with tabs.

Replaces the dashboard.yaml-driven `/page/markets` widget. The widget
framework's strength is repeated cells driven by background refresh; it
struggles with query-param-driven views. This page mirrors the pattern
used by ``views/market_detail.py``: the route in ``mount.py`` is a thin
wrapper around :func:`build_context`, which returns a frozen dataclass
the Jinja template renders directly.

URL: ``GET /markets?view=all|archived&q=&platform=&category=&status=&page=N``

The ``view`` query param drives an in-page tab strip per the
sigil-frontend DESIGN.md "vertical IA" rule (sub-navigation inside the
Markets section instead of new top-level entries):

- ``view=all`` (default) — currently-running markets only
  (``status='open' AND archived=False``).
- ``view=archived`` — non-running markets
  (``status != 'open' OR archived=True``).
- ``view=spreads`` — handled by the route, NOT by this builder; the
  route renders the ``cross_platform_spreads`` widget inline.

Other filters layer on top of the chosen view:

- ``q``: case-insensitive substring match on title (ILIKE %q%).
- ``platform``: exact match on Market.platform (kalshi / polymarket).
- ``category``: exact match on Market.taxonomy_l1.
- ``status``: exact match on Market.status when set. ``status=any``
  removes the per-view status restriction (so the user can scope to a
  specific status within either view).
- ``page``: 1-indexed; we render ``_PAGE_SIZE`` rows per page.

Each row links to ``/market/{external_id}`` for the detail view.

The legacy ``?archived=1`` query param is translated to ``?view=archived``
by the route handler so existing bookmarks keep working.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime
from typing import List, Optional, Tuple
from uuid import UUID

from sqlalchemy import and_, desc, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from sigil.models import Market, MarketPrice


logger = logging.getLogger(__name__)

_PAGE_SIZE = 50
_MAX_PAGE = 1000   # arbitrary safety cap; 50k markets later, revisit

# Tab views recognised by the markets list. ``spreads`` is intercepted
# by the route handler before it reaches build_context — listed here
# so callers can validate / iterate.
VIEWS_RENDERED_AS_TABLE = ("all", "archived")
ALL_VIEWS = ("all", "spreads", "archived")


@dataclass(frozen=True)
class _MarketsRow:
    external_id: str
    title: str
    platform: str
    taxonomy_l1: Optional[str]
    status: str
    archived: bool
    last_price: Optional[float]
    volume_24h: Optional[float]
    last_price_at: Optional[datetime]


@dataclass(frozen=True)
class MarketsListContext:
    rows: List[_MarketsRow]
    total: int
    page: int
    page_size: int
    total_pages: int
    view: str   # "all" | "archived" — "spreads" never reaches here
    # Echoed filter values so the template can pre-fill the form.
    q: str
    platform: str
    category: str
    status: str
    # Distinct-value option lists for select dropdowns.
    platforms: List[str]
    categories: List[str]
    statuses: List[str]


def _coerce_view(v: Optional[str]) -> str:
    """Normalise the ?view= query param. Unknown values fall back to
    'all'. ``spreads`` is recognised here for completeness — the route
    handler intercepts it before build_context runs."""
    if v is None:
        return "all"
    cleaned = v.strip().lower()
    if cleaned in ALL_VIEWS:
        return cleaned
    return "all"


def _coerce_page(v: Optional[str]) -> int:
    try:
        n = int(v) if v else 1
    except (TypeError, ValueError):
        n = 1
    return max(1, min(n, _MAX_PAGE))


async def build_context(
    session: AsyncSession,
    *,
    view: Optional[str] = None,
    q: Optional[str] = None,
    platform: Optional[str] = None,
    category: Optional[str] = None,
    status: Optional[str] = None,
    page: Optional[str] = None,
) -> MarketsListContext:
    """Fetch one filtered + paginated page of markets, plus the
    distinct-value option lists for the filter dropdowns.

    All filter args come straight from query string and may be ``None``
    or empty strings — coerce uniformly here so the route handler stays
    a thin wrapper. ``view`` selects the tab (``all`` or ``archived``);
    ``spreads`` is intercepted by the route handler.
    """
    view_clean = _coerce_view(view)
    if view_clean == "spreads":
        # Defensive: the spreads tab is rendered by the route handler,
        # not by this builder. Fall back to "all" if someone calls
        # build_context directly with view=spreads.
        view_clean = "all"

    q_clean = (q or "").strip()
    platform_clean = (platform or "").strip()
    category_clean = (category or "").strip()
    # Status filter layered on top of the view. An explicit
    # `?status=closed` wins outright; `?status=any` removes the
    # view's status restriction.
    status_clean = (status or "").strip()
    page_n = _coerce_page(page)

    # Base predicate set used by both COUNT and the row query.
    base = select(Market)
    if q_clean:
        base = base.where(Market.title.ilike(f"%{q_clean}%"))
    if platform_clean:
        base = base.where(Market.platform == platform_clean)
    if category_clean:
        base = base.where(Market.taxonomy_l1 == category_clean)

    # Explicit status pick (e.g. ?status=closed) wins outright. "any"
    # disables the per-view status filter altogether.
    if status_clean and status_clean != "any":
        base = base.where(Market.status == status_clean)

    # View toggle — "All" (default) shows currently-running markets;
    # "Archived" inverts to non-running. The user's mental model is
    # "live vs no longer running" — gamma's narrow archived flag and
    # status != 'open' both count as "no longer running". Status filter
    # layers on top: a specific value (e.g. ?status=closed) narrows the
    # SQL further; "any" drops the per-view status restriction but
    # keeps the per-view archived-flag scope.
    if view_clean == "all":
        # Default tab semantics: enforce status=open unless the user
        # explicitly opts out via ?status=any (or picks a specific
        # status, in which case the earlier `status == status_clean`
        # filter is what's running).
        if not status_clean:
            base = base.where(Market.status == "open")
        # archived=False is the entire point of the "All" tab.
        base = base.where(Market.archived == False)  # noqa: E712
    else:  # view_clean == "archived"
        if status_clean == "open":
            # The user picked status=open on the Archived tab — keep
            # the "non-running" feel by restricting to gamma-archived
            # rows (the only way an open market lands here).
            base = base.where(Market.archived == True)  # noqa: E712
        elif not status_clean or status_clean == "any":
            # Default / "any" → "not running" = status != open OR
            # gamma-archived.
            base = base.where(
                or_(Market.status != "open", Market.archived == True)  # noqa: E712
            )
        # else: user picked a specific non-open status (e.g.
        # "closed"). That's inherently non-running, no extra scope
        # needed.

    total = (await session.execute(
        select(func.count()).select_from(base.subquery())
    )).scalar_one()

    rows_q = (
        base.order_by(Market.platform.asc(), Market.title.asc())
        .offset((page_n - 1) * _PAGE_SIZE)
        .limit(_PAGE_SIZE)
    )
    markets = (await session.execute(rows_q)).scalars().all()

    # Latest-price lookup per market shown on this page only — keeps the
    # query count bounded at PAGE_SIZE.
    rows: List[_MarketsRow] = []
    for m in markets:
        price = (await session.execute(
            select(MarketPrice)
            .where(MarketPrice.market_id == m.id)
            .order_by(desc(MarketPrice.time))
            .limit(1)
        )).scalar_one_or_none()
        rows.append(_MarketsRow(
            external_id=m.external_id,
            title=m.title,
            platform=m.platform,
            taxonomy_l1=m.taxonomy_l1,
            status=m.status,
            # "archived" for display purposes = no longer running. Either
            # the gamma flag is set or the market is no longer open.
            archived=bool(m.archived) or m.status != "open",
            last_price=float(price.last_price) if price and price.last_price is not None else None,
            volume_24h=float(price.volume_24h) if price and price.volume_24h is not None else None,
            last_price_at=price.time if price else None,
        ))

    # Distinct-value lists for the filter dropdowns. Cheap on a 258-row
    # table; revisit if Market grows past O(100k).
    platforms = sorted(
        v for v, in (await session.execute(
            select(Market.platform).distinct()
        )).all() if v
    )
    categories = sorted(
        v for v, in (await session.execute(
            select(Market.taxonomy_l1).distinct()
        )).all() if v
    )
    statuses = sorted(
        v for v, in (await session.execute(
            select(Market.status).distinct()
        )).all() if v
    )

    total_pages = max(1, (total + _PAGE_SIZE - 1) // _PAGE_SIZE)
    return MarketsListContext(
        rows=rows,
        total=int(total),
        page=page_n,
        page_size=_PAGE_SIZE,
        total_pages=total_pages,
        view=view_clean,
        q=q_clean,
        platform=platform_clean,
        category=category_clean,
        status=status_clean,
        platforms=platforms,
        categories=categories,
        statuses=statuses,
    )
