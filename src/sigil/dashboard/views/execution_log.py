"""Execution log page — server-side filtered + paginated orders feed.

Mirrors :mod:`sigil.dashboard.views.markets_list` (filterable list view,
Jinja-rendered, no widget framework). The route in ``mount.py`` is a thin
wrapper around :func:`build_context`.

URL: ``GET /execution?platform=&mode=&status=&page=N``

- ``platform``: exact match on Order.platform.
- ``mode``: ``paper`` or ``live``. Filters Order.mode.
- ``status``: exact match on Order.status (created/filled/cancelled/...).
- ``page``: 1-indexed; ``_PAGE_SIZE`` rows per page.

Each row links to ``/market/{external_id}`` via the joined Market.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime
from typing import List, Optional
from uuid import UUID

from sqlalchemy import desc, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from sigil.models import Market, Order


logger = logging.getLogger(__name__)

_PAGE_SIZE = 50
_MAX_PAGE = 1000


@dataclass(frozen=True)
class _OrderRow:
    id: str
    created_at: Optional[datetime]
    platform: str
    market_id: UUID
    market_external_id: str
    market_title: str
    mode: str            # "paper" or "live"
    side: str            # "buy" or "sell"
    outcome: str         # "yes" or "no"
    order_type: str
    quantity: int
    filled_quantity: int
    price: float
    avg_fill_price: Optional[float]
    edge_at_entry: Optional[float]
    status: str


@dataclass(frozen=True)
class ExecutionLogContext:
    rows: List[_OrderRow]
    total: int
    page: int
    page_size: int
    total_pages: int
    # Echoed filter values so the template can pre-fill the form.
    platform: str
    mode: str
    status: str
    # Distinct-value option lists for select dropdowns.
    platforms: List[str]
    modes: List[str]
    statuses: List[str]


def _coerce_page(v: Optional[str]) -> int:
    try:
        n = int(v) if v else 1
    except (TypeError, ValueError):
        n = 1
    return max(1, min(n, _MAX_PAGE))


async def build_context(
    session: AsyncSession,
    *,
    platform: Optional[str] = None,
    mode: Optional[str] = None,
    status: Optional[str] = None,
    page: Optional[str] = None,
) -> ExecutionLogContext:
    """Fetch one filtered + paginated page of orders, plus the
    distinct-value option lists for the filter dropdowns.

    All filter args come straight from query string and may be ``None``
    or empty strings — coerce uniformly here so the route handler stays
    thin.
    """
    platform_clean = (platform or "").strip()
    mode_clean = (mode or "").strip()
    status_clean = (status or "").strip()
    page_n = _coerce_page(page)

    base = select(Order)
    if platform_clean:
        base = base.where(Order.platform == platform_clean)
    if mode_clean:
        base = base.where(Order.mode == mode_clean)
    if status_clean:
        base = base.where(Order.status == status_clean)

    total = (await session.execute(
        select(func.count()).select_from(base.subquery())
    )).scalar_one()

    rows_q = (
        base.order_by(desc(Order.created_at))
        .offset((page_n - 1) * _PAGE_SIZE)
        .limit(_PAGE_SIZE)
    )
    orders = (await session.execute(rows_q)).scalars().all()

    # Resolve market metadata for the orders shown on this page only.
    market_ids = {o.market_id for o in orders}
    markets_by_id: dict[UUID, Market] = {}
    if market_ids:
        market_rows = (await session.execute(
            select(Market).where(Market.id.in_(market_ids))
        )).scalars().all()
        markets_by_id = {m.id: m for m in market_rows}

    rows: List[_OrderRow] = []
    for o in orders:
        m = markets_by_id.get(o.market_id)
        rows.append(_OrderRow(
            id=str(o.id),
            created_at=o.created_at,
            platform=o.platform,
            market_id=o.market_id,
            market_external_id=m.external_id if m else "",
            market_title=m.title if m else "(market not found)",
            mode=o.mode,
            side=o.side,
            outcome=o.outcome,
            order_type=o.order_type,
            quantity=int(o.quantity),
            filled_quantity=int(o.filled_quantity),
            price=float(o.price),
            avg_fill_price=float(o.avg_fill_price) if o.avg_fill_price is not None else None,
            edge_at_entry=float(o.edge_at_entry) if o.edge_at_entry is not None else None,
            status=o.status,
        ))

    platforms = sorted(
        v for v, in (await session.execute(
            select(Order.platform).distinct()
        )).all() if v
    )
    modes = sorted(
        v for v, in (await session.execute(
            select(Order.mode).distinct()
        )).all() if v
    )
    statuses = sorted(
        v for v, in (await session.execute(
            select(Order.status).distinct()
        )).all() if v
    )

    total_pages = max(1, (total + _PAGE_SIZE - 1) // _PAGE_SIZE)
    return ExecutionLogContext(
        rows=rows,
        total=int(total),
        page=page_n,
        page_size=_PAGE_SIZE,
        total_pages=total_pages,
        platform=platform_clean,
        mode=mode_clean,
        status=status_clean,
        platforms=platforms,
        modes=modes,
        statuses=statuses,
    )
