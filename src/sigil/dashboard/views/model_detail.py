"""Model detail page — query + context builder.

One page per registered model keyed by ``model_id``. Renders:

1. Header with display name, version, status, tags, description.
2. Stats row: trades, win rate, realized/unrealized PnL, drawdown, last trade.
3. Equity curve (cumulative realized PnL over closing events).
4. Recent trades table.
5. Recent predictions table.

The heavy lifting (joins across Prediction/Order/Position) lives in
:mod:`sigil.api.model_performance` — the JSON API and this server-rendered
view share the same aggregation so they can never disagree.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any, Dict, List, Optional

from sqlalchemy.ext.asyncio import AsyncSession

from sigil.api import model_performance as mp
from sigil.dashboard.config import Theme
from sigil.dashboard.widgets.charts import render_roi_curve_svg
from sigil.models_registry import get_model


@dataclass(frozen=True)
class ModelDetailContext:
    model_id: str
    version: str
    display_name: str
    description: str
    tags: List[str]
    enabled: bool
    summary: Dict[str, Any]
    equity_curve_svg: str
    equity_curve_points: int
    recent_trades: List[Dict[str, Any]]
    recent_predictions: List[Dict[str, Any]]


async def build_context(
    session: AsyncSession,
    model_id: str,
    *,
    theme: Optional[Theme] = None,
) -> Optional[ModelDetailContext]:
    """Fetch everything for one model detail page. Returns ``None`` when the
    model is not registered (route handler returns 404)."""
    if get_model(model_id) is None:
        return None
    detail = await mp.model_detail(session, model_id)
    if detail is None:
        return None

    # mp.model_equity_curve returns [{"t": iso_str, "cum_pnl": float}, ...].
    # render_roi_curve_svg expects [(timestamp, equity), ...] — convert.
    raw_curve = detail.get("equity_curve") or []
    curve_tuples: List[tuple] = [
        (point.get("t"), float(point.get("cum_pnl", 0.0))) for point in raw_curve
    ]
    equity_svg = render_roi_curve_svg(curve_tuples, theme=theme)

    return ModelDetailContext(
        model_id=detail["model_id"],
        version=detail["version"],
        display_name=detail["display_name"],
        description=detail.get("description") or "",
        tags=list(detail.get("tags") or []),
        enabled=bool(detail.get("enabled", True)),
        summary=detail.get("summary") or {},
        equity_curve_svg=equity_svg,
        equity_curve_points=len(curve_tuples),
        recent_trades=list(detail.get("recent_trades") or []),
        recent_predictions=list(detail.get("recent_predictions") or []),
    )
