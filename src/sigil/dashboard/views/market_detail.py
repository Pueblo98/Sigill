"""Market detail page — query + context builder.

One page per market keyed by ``external_id``. Renders:

1. Header with title, platform, category, status, resolution date,
   plus the latest Prediction's edge as a top-line stat.
2. Latest price + 7-day sparkline.
3. Predictions table with PredictionFeature chips ("mediating factor").
4. Trade lifecycle (Orders + Positions for this market, time-ordered).
5. Similar markets sidebar — same Kalshi event prefix or same
   taxonomy.

All queries run on the AsyncSession passed in by the route handler.
The route is registered in ``mount._register_routes``.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional, Sequence
from uuid import UUID

from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from sigil.dashboard.config import Theme
from sigil.dashboard.widgets.charts import render_price_sparkline_svg
from sigil.models import (
    Market,
    MarketPrice,
    Order,
    Position,
    Prediction,
    PredictionFeature,
)


logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class _PredictionView:
    id: str
    model_id: str
    model_version: str
    predicted_prob: Optional[float]
    market_price_at_prediction: Optional[float]
    edge: Optional[float]
    confidence: Optional[float]
    created_at: datetime
    features: List[Dict[str, Any]]   # [{name, value, version}, ...]


@dataclass(frozen=True)
class _LifecycleEntry:
    when: datetime
    kind: str               # "order" | "position"
    action: str             # human label
    side: Optional[str]
    outcome: Optional[str]
    quantity: Optional[int]
    price: Optional[float]
    status: str
    realized_pnl: Optional[float]


@dataclass(frozen=True)
class _Breadcrumb:
    """Series → event → market hierarchy parsed from the external_id.

    Kalshi tickers nest as ``<SERIES>-<EVENT_DATE_TEAMS>-<MARKET_LEG>``;
    we render this as breadcrumb links in the header so the operator
    can graph-walk up to sibling events / series. Polymarket external
    ids don't carry this structure — both fields stay None there.
    """
    series: Optional[str]
    event: Optional[str]
    ticker: str            # the full external_id


@dataclass(frozen=True)
class _SimilarMarket:
    external_id: str
    title: str
    platform: str
    last_price: Optional[float]
    volume_24h: Optional[float]


@dataclass(frozen=True)
class MarketDetailContext:
    market: Market
    breadcrumb: _Breadcrumb
    latest_price: Optional[MarketPrice]
    sparkline_svg: str
    latest_prediction: Optional[_PredictionView]
    predictions: List[_PredictionView]
    lifecycle: List[_LifecycleEntry]
    siblings_event: List[_SimilarMarket]      # same event prefix
    siblings_taxonomy: List[_SimilarMarket]   # same taxonomy_l1


def _parse_breadcrumb(market: Market) -> _Breadcrumb:
    """Extract series + event from the external_id when possible.

    Kalshi: ``KXNBAGAME-26MAY01CLETOR-CLE`` -> series ``KXNBAGAME``,
    event ``KXNBAGAME-26MAY01CLETOR``. Polymarket / others: no
    structure to extract, both stay None.
    """
    ext = market.external_id
    if market.platform != "kalshi" or ext.count("-") < 2:
        return _Breadcrumb(series=None, event=None, ticker=ext)
    parts = ext.split("-")
    return _Breadcrumb(
        series=parts[0],
        event="-".join(parts[:2]),
        ticker=ext,
    )


# How many days of price history to show in the sparkline.
_SPARKLINE_DAYS = 7
# Size limits keep the page responsive.
_MAX_PREDICTIONS = 50
_MAX_LIFECYCLE_ROWS = 200
_MAX_SIBLINGS_PER_TIER = 10


async def build_context(
    session: AsyncSession,
    external_id: str,
    *,
    theme: Optional[Theme] = None,
) -> Optional[MarketDetailContext]:
    """Fetch everything for one market detail page. Returns None when
    the market doesn't exist (route handler returns 404)."""
    market = (await session.execute(
        select(Market).where(Market.external_id == external_id)
    )).scalar_one_or_none()
    if market is None:
        return None

    latest_price = (await session.execute(
        select(MarketPrice)
        .where(MarketPrice.market_id == market.id)
        .order_by(desc(MarketPrice.time))
        .limit(1)
    )).scalar_one_or_none()

    # 7-day sparkline data: subsample to ~120 points to keep the SVG tiny.
    cutoff = datetime.now(timezone.utc) - timedelta(days=_SPARKLINE_DAYS)
    history_rows = (await session.execute(
        select(MarketPrice.last_price, MarketPrice.bid, MarketPrice.ask)
        .where(MarketPrice.market_id == market.id)
        .where(MarketPrice.time >= cutoff)
        .order_by(MarketPrice.time.asc())
    )).all()
    series: List[float] = []
    for row in history_rows:
        last_p, bid, ask = row
        v = last_p if last_p is not None else (
            ((float(bid) + float(ask)) / 2.0) if (bid is not None and ask is not None) else None
        )
        if v is not None:
            series.append(float(v))
    if len(series) > 120:
        step = max(1, len(series) // 120)
        series = series[::step]
    sparkline_svg = render_price_sparkline_svg(series, theme=theme)

    predictions = await _load_predictions(session, market.id)
    lifecycle = await _load_lifecycle(session, market.id)
    siblings_event, siblings_taxonomy = await _load_siblings(session, market)

    latest_prediction = predictions[0] if predictions else None

    return MarketDetailContext(
        market=market,
        breadcrumb=_parse_breadcrumb(market),
        latest_price=latest_price,
        sparkline_svg=sparkline_svg,
        latest_prediction=latest_prediction,
        predictions=predictions,
        lifecycle=lifecycle,
        siblings_event=siblings_event,
        siblings_taxonomy=siblings_taxonomy,
    )


async def _load_predictions(
    session: AsyncSession, market_id: UUID
) -> List[_PredictionView]:
    rows = (await session.execute(
        select(Prediction)
        .where(Prediction.market_id == market_id)
        .order_by(desc(Prediction.created_at))
        .limit(_MAX_PREDICTIONS)
    )).scalars().all()
    if not rows:
        return []
    pred_ids = [r.id for r in rows]
    feat_rows = (await session.execute(
        select(PredictionFeature)
        .where(PredictionFeature.prediction_id.in_(pred_ids))
    )).scalars().all()
    by_pred: Dict[UUID, List[Dict[str, Any]]] = {}
    for f in feat_rows:
        by_pred.setdefault(f.prediction_id, []).append(
            {"name": f.feature_name, "value": float(f.value), "version": int(f.version)}
        )

    out: List[_PredictionView] = []
    for r in rows:
        out.append(_PredictionView(
            id=str(r.id),
            model_id=r.model_id,
            model_version=r.model_version,
            predicted_prob=float(r.predicted_prob) if r.predicted_prob is not None else None,
            market_price_at_prediction=float(r.market_price_at_prediction)
                if r.market_price_at_prediction is not None else None,
            edge=float(r.edge) if r.edge is not None else None,
            confidence=float(r.confidence) if r.confidence is not None else None,
            created_at=r.created_at,
            features=sorted(by_pred.get(r.id, []), key=lambda f: f["name"]),
        ))
    return out


async def _load_lifecycle(
    session: AsyncSession, market_id: UUID
) -> List[_LifecycleEntry]:
    orders = (await session.execute(
        select(Order)
        .where(Order.market_id == market_id)
        .order_by(desc(Order.created_at))
        .limit(_MAX_LIFECYCLE_ROWS)
    )).scalars().all()
    positions = (await session.execute(
        select(Position)
        .where(Position.market_id == market_id)
        .order_by(desc(Position.opened_at))
        .limit(_MAX_LIFECYCLE_ROWS)
    )).scalars().all()

    entries: List[_LifecycleEntry] = []
    for o in orders:
        entries.append(_LifecycleEntry(
            when=o.created_at,
            kind="order",
            action=f"order {o.status}",
            side=o.side,
            outcome=o.outcome,
            quantity=o.quantity,
            price=float(o.avg_fill_price) if o.avg_fill_price is not None else float(o.price),
            status=o.status,
            realized_pnl=None,
        ))
    for p in positions:
        # One synthetic entry for the position itself; closed positions
        # also get a "closed" row so the timeline shows both endpoints.
        entries.append(_LifecycleEntry(
            when=p.opened_at,
            kind="position",
            action="position opened",
            side=None,
            outcome=p.outcome,
            quantity=p.quantity,
            price=float(p.avg_entry_price),
            status=p.status,
            realized_pnl=None,
        ))
        if p.status in ("closed", "settled") and p.closed_at is not None:
            entries.append(_LifecycleEntry(
                when=p.closed_at,
                kind="position",
                action=f"position {p.status}",
                side=None,
                outcome=p.outcome,
                quantity=p.quantity,
                price=float(p.current_price) if p.current_price is not None else float(p.avg_entry_price),
                status=p.status,
                realized_pnl=float(p.realized_pnl) if p.realized_pnl is not None else None,
            ))
    entries.sort(key=lambda e: e.when, reverse=True)
    return entries[:_MAX_LIFECYCLE_ROWS]


async def _load_siblings(
    session: AsyncSession, market: Market
) -> tuple[List[_SimilarMarket], List[_SimilarMarket]]:
    """Two-tier sibling discovery.

    Tier 1 (same event): Kalshi markets sharing the same prefix up to
    the second '-'. e.g. KXNBAGAME-26MAY01CLETOR-CLE groups all markets
    with prefix KXNBAGAME-26MAY01CLETOR-. Polymarket falls through to
    tier 2 (no clean event grouping in the bare external_id).

    Tier 2 (same taxonomy): top-N other markets sharing taxonomy_l1.
    """
    siblings_event: List[_SimilarMarket] = []
    if market.platform == "kalshi" and market.external_id.count("-") >= 2:
        event_prefix = market.external_id.rsplit("-", 1)[0] + "-"
        rows = (await session.execute(
            select(Market)
            .where(Market.platform == "kalshi")
            .where(Market.external_id.like(f"{event_prefix}%"))
            .where(Market.id != market.id)
            .where(Market.status == "open")
            .limit(_MAX_SIBLINGS_PER_TIER)
        )).scalars().all()
        siblings_event = [await _to_similar(session, m) for m in rows]

    seen_ids = {market.id} | {sibling_id for sibling_id in
                              [_lookup_id(session, s.external_id) for s in []]}
    rows = (await session.execute(
        select(Market)
        .where(Market.taxonomy_l1 == market.taxonomy_l1)
        .where(Market.id != market.id)
        .where(Market.status == "open")
        .limit(_MAX_SIBLINGS_PER_TIER * 4)
    )).scalars().all()
    siblings_tax: List[_SimilarMarket] = []
    seen_external = {s.external_id for s in siblings_event}
    for m in rows:
        if m.external_id in seen_external:
            continue
        siblings_tax.append(await _to_similar(session, m))
        if len(siblings_tax) >= _MAX_SIBLINGS_PER_TIER:
            break
    return siblings_event, siblings_tax


async def _to_similar(session: AsyncSession, market: Market) -> _SimilarMarket:
    price = (await session.execute(
        select(MarketPrice)
        .where(MarketPrice.market_id == market.id)
        .order_by(desc(MarketPrice.time))
        .limit(1)
    )).scalar_one_or_none()
    return _SimilarMarket(
        external_id=market.external_id,
        title=market.title,
        platform=market.platform,
        last_price=float(price.last_price) if price and price.last_price is not None else None,
        volume_24h=float(price.volume_24h) if price and price.volume_24h is not None else None,
    )


def _lookup_id(_session, _ext_id):  # vestigial helper kept for shape parity
    return None
