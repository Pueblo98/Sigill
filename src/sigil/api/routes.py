from __future__ import annotations

import asyncio
import logging
import time
from dataclasses import asdict, is_dataclass
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import String, cast, desc, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from sigil.config import config
from sigil.db import get_db
from sigil.models import (
    BankrollSnapshot,
    Market,
    MarketPrice,
    Order,
    Position,
    Prediction,
    SourceHealth,
)
from sigil.api import model_performance as mp
# Importing the signal modules here registers their ModelDefs in
# `sigil.models_registry`. Without this import path, /api/models would
# return an empty list because the registrations happen at module import.
from sigil.signals import spread_arb as _spread_arb_register  # noqa: F401
from sigil.signals import elo_sports as _elo_sports_register  # noqa: F401
from sigil.models_registry import get_model

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api")


# In-process TTL cache for stat-arb scan results.
# Hitting Kalshi + Polymarket REST on every dashboard poll would be abusive;
# the scan is deterministic enough that a 60s window is fine. The asyncio
# Lock is a single-flight guard — without it, SWR polls every 5s while a
# scan takes >60s, so requests stack up and each kicks off its own
# Polymarket CLOB enumeration (hammers their API + starves the worker).
_ARB_CACHE_TTL_SECONDS = 60.0
_arb_cache: Dict[str, Any] = {"ts": 0.0, "data": []}
_arb_scan_lock = asyncio.Lock()


def _opp_to_dict(opp: Any) -> Dict[str, Any]:
    """Convert a stat_arb.ArbOpportunity (dataclass) into a JSON-friendly dict
    matching the frontend table shape."""
    k = getattr(opp, "kalshi", None)
    p = getattr(opp, "polymarket", None)
    if k is None or p is None:
        # Best-effort fallback if the engine ever returns plain dicts
        return asdict(opp) if is_dataclass(opp) else dict(opp)

    def _cents(x: Optional[float]) -> float:
        return float(x) * 100.0 if x is not None else 0.0

    return {
        "event": k.title,
        "kalshi_ticker": (k.external_id or "")[:12],
        "poly_ticker": (p.external_id or "")[:12],
        "kalshi_bid": _cents(k.yes_bid),
        "kalshi_ask": _cents(k.yes_ask),
        "kalshi_min_size": 1000,
        "poly_bid": _cents(p.yes_bid),
        "poly_ask": _cents(p.yes_ask),
        "poly_min_size": 1000,
        "implied_sum": _cents(opp.gross_cost),
        "net_arb": float(opp.net_profit) * 100.0,
        "match_score": float(opp.match_score),
        "opportunity_type": opp.opportunity_type,
        "kelly_size": float(opp.kelly_size),
        "display_only": True,
    }


@router.get("/portfolio")
async def get_portfolio(db: AsyncSession = Depends(get_db)) -> Dict[str, Any]:
    """Latest bankroll snapshot for the default mode. No fabrication: when no
    snapshot exists we return zeros plus a `state: 'no_data'` flag so the UI
    can render an empty state instead of misleading numbers."""
    q = (
        select(BankrollSnapshot)
        .where(BankrollSnapshot.mode == config.DEFAULT_MODE)
        .order_by(desc(BankrollSnapshot.time))
        .limit(1)
    )
    row = (await db.execute(q)).scalars().first()
    if row is None:
        return {
            "state": "no_data",
            "mode": config.DEFAULT_MODE,
            "balance": 0.0,
            "roi": 0.0,
            "unrealized_pnl": 0.0,
            "realized_pnl": 0.0,
            "settled_trades_total": 0,
            "settled_trades_30d": 0,
            "as_of": None,
        }

    initial = config.BANKROLL_INITIAL or 0.0
    roi = ((float(row.equity) - initial) / initial * 100.0) if initial else 0.0

    return {
        "state": "ok",
        "mode": row.mode,
        "balance": float(row.equity),
        "roi": roi,
        "unrealized_pnl": float(row.unrealized_pnl_total),
        "realized_pnl": float(row.realized_pnl_total),
        "settled_trades_total": int(row.settled_trades_total),
        "settled_trades_30d": int(row.settled_trades_30d),
        "as_of": row.time.isoformat(),
    }


@router.get("/markets")
async def get_markets(db: AsyncSession = Depends(get_db)) -> List[Dict[str, Any]]:
    q = select(Market).where(Market.status == "open").limit(50)
    markets = (await db.execute(q)).scalars().all()
    return [
        {
            "id": str(m.id),
            "platform": m.platform,
            "title": m.title,
            "resolution_date": m.resolution_date.isoformat() if m.resolution_date else None,
            "external_id": m.external_id,
            "market_type": m.market_type,
            "taxonomy_l1": m.taxonomy_l1,
            "taxonomy_l2": m.taxonomy_l2,
            "status": m.status,
        }
        for m in markets
    ]


@router.get("/markets/{market_id}")
async def get_market(market_id: str, db: AsyncSession = Depends(get_db)) -> Dict[str, Any]:
    """Fetch market by either external_id or UUID. Price lookup uses the UUID
    (Market.id), NOT the external_id — fixes the prior FK-type bug."""
    m_query = await db.execute(select(Market).where(Market.external_id == market_id))
    m = m_query.scalars().first()
    if not m:
        m_query = await db.execute(select(Market).where(cast(Market.id, String) == market_id))
        m = m_query.scalars().first()
        if not m:
            raise HTTPException(status_code=404, detail="Market not found")

    p_query = await db.execute(
        select(MarketPrice)
        .where(MarketPrice.market_id == m.id)
        .order_by(desc(MarketPrice.time))
        .limit(1)
    )
    price = p_query.scalars().first()

    return {
        "id": str(m.id),
        "platform": m.platform,
        "title": m.title,
        "resolution_date": m.resolution_date.isoformat() if m.resolution_date else None,
        "external_id": m.external_id,
        "market_type": m.market_type,
        "taxonomy_l1": m.taxonomy_l1,
        "taxonomy_l2": m.taxonomy_l2,
        "status": m.status,
        "bid": float(price.bid) if price and price.bid is not None else None,
        "ask": float(price.ask) if price and price.ask is not None else None,
        "last_price": float(price.last_price) if price and price.last_price is not None else None,
        "volume_24h": float(price.volume_24h) if price and price.volume_24h is not None else None,
        "last_updated": price.time.isoformat() if price else None,
    }


@router.get("/positions")
async def get_positions(db: AsyncSession = Depends(get_db)) -> List[Dict[str, Any]]:
    q = (
        select(Position, Market)
        .join(Market, Market.id == Position.market_id)
        .where(Position.status == "open", Position.mode == config.DEFAULT_MODE)
        .order_by(desc(Position.opened_at))
    )
    rows = (await db.execute(q)).all()
    return [
        {
            "id": str(pos.id),
            "platform": pos.platform,
            "market_id": str(pos.market_id),
            "market_title": mkt.title,
            "external_id": mkt.external_id,
            "mode": pos.mode,
            "outcome": pos.outcome,
            "quantity": int(pos.quantity),
            "avg_entry_price": float(pos.avg_entry_price),
            "current_price": float(pos.current_price) if pos.current_price is not None else None,
            "unrealized_pnl": float(pos.unrealized_pnl) if pos.unrealized_pnl is not None else None,
            "realized_pnl": float(pos.realized_pnl),
            "status": pos.status,
            "opened_at": pos.opened_at.isoformat() if pos.opened_at else None,
        }
        for pos, mkt in rows
    ]


@router.get("/orders")
async def get_orders(
    db: AsyncSession = Depends(get_db),
    limit: int = Query(default=50, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
) -> List[Dict[str, Any]]:
    q = (
        select(Order)
        .order_by(desc(Order.created_at))
        .offset(offset)
        .limit(limit)
    )
    orders = (await db.execute(q)).scalars().all()
    return [
        {
            "id": str(o.id),
            "client_order_id": o.client_order_id,
            "external_order_id": o.external_order_id,
            "platform": o.platform,
            "market_id": str(o.market_id),
            "mode": o.mode,
            "side": o.side,
            "outcome": o.outcome,
            "order_type": o.order_type,
            "price": float(o.price),
            "quantity": int(o.quantity),
            "filled_quantity": int(o.filled_quantity),
            "avg_fill_price": float(o.avg_fill_price) if o.avg_fill_price is not None else None,
            "fees": float(o.fees),
            "edge_at_entry": float(o.edge_at_entry) if o.edge_at_entry is not None else None,
            "status": o.status,
            "created_at": o.created_at.isoformat() if o.created_at else None,
        }
        for o in orders
    ]


@router.get("/predictions")
async def get_predictions(
    db: AsyncSession = Depends(get_db),
    model_id: Optional[str] = Query(default=None),
    limit: int = Query(default=50, ge=1, le=500),
) -> List[Dict[str, Any]]:
    q = select(Prediction).order_by(desc(Prediction.created_at)).limit(limit)
    if model_id:
        q = q.where(Prediction.model_id == model_id)
    preds = (await db.execute(q)).scalars().all()
    return [
        {
            "id": str(p.id),
            "market_id": str(p.market_id),
            "model_id": p.model_id,
            "model_version": p.model_version,
            "predicted_prob": float(p.predicted_prob),
            "confidence": float(p.confidence) if p.confidence is not None else None,
            "market_price_at_prediction": float(p.market_price_at_prediction)
            if p.market_price_at_prediction is not None
            else None,
            "edge": float(p.edge) if p.edge is not None else None,
            "created_at": p.created_at.isoformat() if p.created_at else None,
        }
        for p in preds
    ]


@router.get("/health")
async def get_health(db: AsyncSession = Depends(get_db)) -> Dict[str, Any]:
    """Aggregate `SourceHealth` rows by source: latest status, 24h error count,
    p50/p95 latency over the last 24h."""
    from datetime import datetime, timedelta, timezone

    cutoff = datetime.now(timezone.utc) - timedelta(hours=24)

    rows = (
        await db.execute(
            select(SourceHealth).where(SourceHealth.check_time >= cutoff)
        )
    ).scalars().all()

    by_source: Dict[str, List[SourceHealth]] = {}
    for r in rows:
        by_source.setdefault(r.source_name, []).append(r)

    sources = []
    for name, group in by_source.items():
        group_sorted = sorted(group, key=lambda r: r.check_time, reverse=True)
        latest = group_sorted[0]
        error_count_24h = sum(1 for r in group if r.status not in ("ok", "healthy"))
        latencies = sorted(int(r.latency_ms) for r in group if r.latency_ms is not None)

        def _percentile(arr: List[int], pct: float) -> Optional[int]:
            if not arr:
                return None
            idx = max(0, min(len(arr) - 1, int(round((pct / 100.0) * (len(arr) - 1)))))
            return arr[idx]

        sources.append(
            {
                "source_name": name,
                "status": latest.status,
                "error_count_24h": error_count_24h,
                "latency_p50_ms": _percentile(latencies, 50),
                "latency_p95_ms": _percentile(latencies, 95),
                "records_fetched_latest": int(latest.records_fetched)
                if latest.records_fetched is not None
                else None,
                "last_checked": latest.check_time.isoformat() if latest.check_time else None,
                "last_error": latest.error_message,
            }
        )

    sources.sort(key=lambda s: s["source_name"])
    return {
        "state": "ok" if sources else "no_data",
        "sources": sources,
        "as_of": rows[0].check_time.isoformat() if rows else None,
    }


@router.get("/models")
async def get_models(db: AsyncSession = Depends(get_db)) -> List[Dict[str, Any]]:
    """List every registered model with summary metrics. Models that
    haven't yet emitted a prediction still appear (with ``state: 'no_data'``
    in their summary) so the UI can surface them as "no signals yet" cards.
    """
    return await mp.all_model_summaries(db)


@router.get("/models/{model_id}")
async def get_model_detail(
    model_id: str, db: AsyncSession = Depends(get_db)
) -> Dict[str, Any]:
    """Full per-model bundle: metadata + summary + equity curve +
    recent trades + recent predictions. 404 if the model is not registered.
    """
    if get_model(model_id) is None:
        raise HTTPException(status_code=404, detail="Model not found")
    detail = await mp.model_detail(db, model_id)
    if detail is None:
        # Defensive: get_model said yes, model_detail said no — shouldn't happen.
        raise HTTPException(status_code=404, detail="Model not found")
    return detail


@router.get("/arbitrage")
async def get_arbitrage() -> List[Dict[str, Any]]:
    """Cross-platform stat-arb opportunities from `decision.stat_arb.StatArbScanner`.
    Cached for 60s in-process. DISPLAY ONLY per REVIEW-DECISIONS.md 1C.

    Single-flight: at most one StatArbScanner.scan() runs at a time even
    when SWR polling stacks N concurrent requests waiting on a slow
    (>60s) Polymarket CLOB enumeration. Followers grab the freshly
    populated cache after the leader returns.
    """
    now = time.monotonic()
    if (now - _arb_cache["ts"]) < _ARB_CACHE_TTL_SECONDS and _arb_cache["data"]:
        return _arb_cache["data"]

    async with _arb_scan_lock:
        # Re-check after acquiring the lock — a previous holder may have
        # populated the cache while we were waiting.
        now = time.monotonic()
        if (now - _arb_cache["ts"]) < _ARB_CACHE_TTL_SECONDS and _arb_cache["data"]:
            return _arb_cache["data"]

        # Imported lazily so the API can boot even if the decision module is mid-edit.
        from sigil.decision.stat_arb import StatArbScanner

        scanner = StatArbScanner()
        try:
            opps = await scanner.scan()
        except Exception as exc:
            logger.warning(f"stat-arb scan failed: {exc}")
            if _arb_cache["data"]:
                return _arb_cache["data"]
            return []

        serialized = [_opp_to_dict(o) for o in opps]
        _arb_cache["ts"] = now
        _arb_cache["data"] = serialized
        return serialized
