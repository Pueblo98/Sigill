"""Per-model performance aggregation.

Joins ``Prediction → Order → Position`` to compute model-level metrics
(trades, win rate, realized/unrealized P&L, max drawdown, equity curve)
for the ``/api/models`` endpoints.

Attribution model
-----------------
``Position`` rows have no direct FK to ``Order`` / ``Prediction``. They
are keyed on ``(platform, market_id, outcome, mode)`` and accumulate
across every order that touches that tuple. We attribute a Position to
a model when **any** opening (``side='buy'``) order on that tuple is
linked to a Prediction with ``model_id == model_id``. With one model
active per market+outcome (the current reality) this is exact; if two
models ever trade the same market+outcome+mode the realized P&L would
be aliased — call it a TODO once that happens.

Equity curve
------------
We chart **closing-event realized P&L** (cumulative). Each closed
Position contributes one point at its ``closed_at`` time equal to its
``realized_pnl``. Open positions never appear on the curve (their P&L
is still unrealized). Empty case: no closed positions → empty curve;
the frontend handles the empty state.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any, Optional

from sqlalchemy import and_, desc, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from sigil.models import Market, Order, Position, Prediction
from sigil.models_registry import ModelDef, all_models, get_model


# ---- internal helpers -----------------------------------------------------


def _model_position_ids_subquery(model_id: str):
    """Subquery returning distinct Position.id values attributable to ``model_id``.

    A Position is attributed when at least one buy Order on the same
    ``(platform, market_id, outcome, mode)`` tuple is linked (via
    ``Order.prediction_id``) to a Prediction whose ``model_id`` matches.
    """
    return (
        select(Position.id)
        .join(
            Order,
            and_(
                Order.platform == Position.platform,
                Order.market_id == Position.market_id,
                Order.outcome == Position.outcome,
                Order.mode == Position.mode,
                Order.side == "buy",
            ),
        )
        .join(Prediction, Prediction.id == Order.prediction_id)
        .where(Prediction.model_id == model_id)
        .distinct()
    )


async def _model_orders(
    session: AsyncSession, model_id: str, *, limit: Optional[int] = None
):
    """Return Orders linked to this model (joined to Prediction), newest first."""
    stmt = (
        select(Order, Market)
        .join(Prediction, Prediction.id == Order.prediction_id)
        .join(Market, Market.id == Order.market_id)
        .where(Prediction.model_id == model_id)
        .order_by(desc(Order.created_at))
    )
    if limit is not None:
        stmt = stmt.limit(limit)
    return (await session.execute(stmt)).all()


# ---- summary --------------------------------------------------------------


async def model_summary(session: AsyncSession, model_id: str) -> dict[str, Any]:
    """Compute the summary stats shown on the model card / detail header.

    Always returns a dict with the same keys, even when there's no data
    (consistent with the ``state: ok | no_data`` convention used by
    ``/api/portfolio``).
    """
    now = datetime.now(timezone.utc)
    cutoff_24h = now - timedelta(hours=24)

    # Predictions: 24h count + total count + most recent edge
    pred_total = (await session.execute(
        select(func.count())
        .select_from(Prediction)
        .where(Prediction.model_id == model_id)
    )).scalar_one()
    pred_24h = (await session.execute(
        select(func.count())
        .select_from(Prediction)
        .where(Prediction.model_id == model_id)
        .where(Prediction.created_at >= cutoff_24h)
    )).scalar_one()

    # Trades: count of *filled* orders linked to this model.
    trades_total = (await session.execute(
        select(func.count())
        .select_from(Order)
        .join(Prediction, Prediction.id == Order.prediction_id)
        .where(Prediction.model_id == model_id)
        .where(Order.status == "filled")
    )).scalar_one()
    last_trade_at = (await session.execute(
        select(func.max(Order.created_at))
        .select_from(Order)
        .join(Prediction, Prediction.id == Order.prediction_id)
        .where(Prediction.model_id == model_id)
        .where(Order.status == "filled")
    )).scalar_one()

    # Position-level P&L for attributed positions.
    position_ids_subq = _model_position_ids_subquery(model_id)
    positions = (await session.execute(
        select(Position).where(Position.id.in_(position_ids_subq))
    )).scalars().all()

    realized_pnl = sum(float(p.realized_pnl or 0.0) for p in positions)
    unrealized_pnl = sum(
        float(p.unrealized_pnl or 0.0) for p in positions if p.status == "open"
    )

    closed = [p for p in positions if p.status == "closed"]
    wins = sum(1 for p in closed if float(p.realized_pnl or 0.0) > 0)
    win_rate = (wins / len(closed)) if closed else None

    # Max drawdown from the closing-events equity curve.
    curve = _equity_curve_from_positions(closed)
    max_drawdown = _max_drawdown(curve)

    has_any_data = pred_total > 0 or trades_total > 0 or len(positions) > 0

    return {
        "predictions_total": int(pred_total),
        "predictions_24h": int(pred_24h),
        "trades_total": int(trades_total),
        "win_rate": round(win_rate, 4) if win_rate is not None else None,
        "realized_pnl": round(realized_pnl, 4),
        "unrealized_pnl": round(unrealized_pnl, 4),
        "max_drawdown": round(max_drawdown, 4) if max_drawdown is not None else None,
        "open_positions": sum(1 for p in positions if p.status == "open"),
        "last_trade_at": last_trade_at.isoformat() if last_trade_at else None,
        "state": "ok" if has_any_data else "no_data",
    }


# ---- equity curve ---------------------------------------------------------


def _equity_curve_from_positions(closed_positions: list[Position]) -> list[dict[str, Any]]:
    """Cumulative realized P&L over time. One point per closed position
    at its ``closed_at`` timestamp, sorted ascending. Each point's
    ``cum_pnl`` is the running sum of ``realized_pnl``.
    """
    events = sorted(
        (p for p in closed_positions if p.closed_at is not None),
        key=lambda p: p.closed_at,
    )
    cum = 0.0
    out: list[dict[str, Any]] = []
    for p in events:
        cum += float(p.realized_pnl or 0.0)
        out.append({
            "t": p.closed_at.isoformat(),
            "cum_pnl": round(cum, 4),
        })
    return out


def _max_drawdown(curve: list[dict[str, Any]]) -> Optional[float]:
    """Peak-to-trough drawdown on cumulative P&L. Returns a non-negative
    value (the magnitude of the worst dip), or ``None`` for empty curves.
    """
    if not curve:
        return None
    peak = curve[0]["cum_pnl"]
    worst = 0.0
    for point in curve:
        v = point["cum_pnl"]
        if v > peak:
            peak = v
        dd = peak - v
        if dd > worst:
            worst = dd
    return worst


async def model_equity_curve(
    session: AsyncSession, model_id: str
) -> list[dict[str, Any]]:
    position_ids_subq = _model_position_ids_subquery(model_id)
    positions = (await session.execute(
        select(Position)
        .where(Position.id.in_(position_ids_subq))
        .where(Position.status == "closed")
    )).scalars().all()
    return _equity_curve_from_positions(list(positions))


# ---- recent trades --------------------------------------------------------


async def model_recent_trades(
    session: AsyncSession, model_id: str, *, limit: int = 50
) -> list[dict[str, Any]]:
    rows = await _model_orders(session, model_id, limit=limit)
    out: list[dict[str, Any]] = []
    for order, market in rows:
        out.append({
            "id": str(order.id),
            "market_id": str(order.market_id),
            "market_title": market.title,
            "external_id": market.external_id,
            "platform": order.platform,
            "side": order.side,
            "outcome": order.outcome,
            "order_type": order.order_type,
            "quantity": int(order.quantity),
            "filled_quantity": int(order.filled_quantity),
            "price": float(order.price),
            "avg_fill_price": float(order.avg_fill_price)
                if order.avg_fill_price is not None else None,
            "edge_at_entry": float(order.edge_at_entry)
                if order.edge_at_entry is not None else None,
            "fees": float(order.fees),
            "status": order.status,
            "mode": order.mode,
            "created_at": order.created_at.isoformat() if order.created_at else None,
        })
    return out


# ---- recent predictions ---------------------------------------------------


async def model_recent_predictions(
    session: AsyncSession, model_id: str, *, limit: int = 50
) -> list[dict[str, Any]]:
    """Recent predictions, with the linked order id (if filled)."""
    stmt = (
        select(Prediction, Order, Market)
        .outerjoin(Order, Order.prediction_id == Prediction.id)
        .join(Market, Market.id == Prediction.market_id)
        .where(Prediction.model_id == model_id)
        .order_by(desc(Prediction.created_at))
        .limit(limit)
    )
    rows = (await session.execute(stmt)).all()
    out: list[dict[str, Any]] = []
    for pred, order, market in rows:
        out.append({
            "id": str(pred.id),
            "market_id": str(pred.market_id),
            "market_title": market.title,
            "external_id": market.external_id,
            "model_id": pred.model_id,
            "model_version": pred.model_version,
            "predicted_prob": float(pred.predicted_prob),
            "confidence": float(pred.confidence) if pred.confidence is not None else None,
            "market_price_at_prediction": float(pred.market_price_at_prediction)
                if pred.market_price_at_prediction is not None else None,
            "edge": float(pred.edge) if pred.edge is not None else None,
            "created_at": pred.created_at.isoformat() if pred.created_at else None,
            "order_id": str(order.id) if order is not None else None,
            "order_status": order.status if order is not None else None,
        })
    return out


# ---- list helpers ---------------------------------------------------------


def _meta_dict(m: ModelDef) -> dict[str, Any]:
    return {
        "model_id": m.model_id,
        "version": m.version,
        "display_name": m.display_name,
        "description": m.description,
        "tags": list(m.tags),
        "enabled": m.enabled,
    }


async def all_model_summaries(session: AsyncSession) -> list[dict[str, Any]]:
    """Summary record for every registered model."""
    out: list[dict[str, Any]] = []
    for m in all_models():
        summary = await model_summary(session, m.model_id)
        out.append({**_meta_dict(m), "summary": summary})
    return out


async def model_detail(
    session: AsyncSession, model_id: str
) -> Optional[dict[str, Any]]:
    """Full detail bundle, or ``None`` if the model is not registered."""
    m = get_model(model_id)
    if m is None:
        return None
    summary = await model_summary(session, model_id)
    curve = await model_equity_curve(session, model_id)
    trades = await model_recent_trades(session, model_id, limit=50)
    preds = await model_recent_predictions(session, model_id, limit=50)
    return {
        **_meta_dict(m),
        "summary": summary,
        "equity_curve": curve,
        "recent_trades": trades,
        "recent_predictions": preds,
    }
