"""model_roi_curve widget.

Cumulative ROI / equity curve per ``model_id``. Settled positions are
linked back to their originating prediction (and thus to a model_id) via
``Order.prediction_id``: each ``Position`` shares the same market+platform
as its order; we look up the most recent order on that triplet to get the
prediction.

Render: SVG line chart through ``charts.render_roi_curve_svg``. Empty
state when no settled positions exist.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any, ClassVar, Dict, List, Optional, Type
from uuid import UUID

from markupsafe import Markup, escape
from sqlalchemy import desc, select

from sigil.dashboard.config import WidgetConfig
from sigil.dashboard.widget import WidgetBase, register_widget
from sigil.dashboard.widgets.charts import render_roi_curve_svg
from sigil.models import Order, Position, Prediction


class ModelRoiCurveConfig(WidgetConfig):
    pass


@dataclass(frozen=True)
class ModelEquityCurve:
    model_id: str
    points: List[tuple]  # (timestamp, equity)
    final_equity: float
    n_trades: int
    svg: str


@register_widget("model_roi_curve")
class ModelRoiCurveWidget(WidgetBase):
    config_model: ClassVar[Type[WidgetConfig]] = ModelRoiCurveConfig

    async def fetch(self, session: Any) -> List[ModelEquityCurve]:
        positions = (
            await session.execute(
                select(Position)
                .where(Position.status.in_(("closed", "settled")))
                .order_by(Position.closed_at)
            )
        ).scalars().all()
        if not positions:
            return []

        # Map (platform, market_id, outcome) -> model_id by walking the
        # most-recent matching order's prediction. Cache per triplet so the
        # query count stays bounded for many same-market positions.
        triplet_to_model: Dict[tuple, Optional[str]] = {}
        for pos in positions:
            key = (pos.platform, pos.market_id, pos.outcome)
            if key in triplet_to_model:
                continue
            order = (
                await session.execute(
                    select(Order)
                    .where(
                        Order.platform == pos.platform,
                        Order.market_id == pos.market_id,
                        Order.outcome == pos.outcome,
                        Order.prediction_id.is_not(None),
                    )
                    .order_by(desc(Order.created_at))
                    .limit(1)
                )
            ).scalars().first()
            model_id: Optional[str] = None
            if order is not None and order.prediction_id is not None:
                pred = (
                    await session.execute(
                        select(Prediction).where(Prediction.id == order.prediction_id)
                    )
                ).scalars().first()
                if pred is not None:
                    model_id = pred.model_id
            triplet_to_model[key] = model_id

        per_model: Dict[str, List[Position]] = {}
        for pos in positions:
            model_id = triplet_to_model.get((pos.platform, pos.market_id, pos.outcome))
            if model_id is None:
                continue
            per_model.setdefault(model_id, []).append(pos)

        if not per_model:
            return []

        out: List[ModelEquityCurve] = []
        for model_id in sorted(per_model.keys()):
            ordered = sorted(
                per_model[model_id],
                key=lambda p: p.closed_at or p.opened_at or datetime.min,
            )
            running = 0.0
            points: List[tuple] = []
            for pos in ordered:
                running += float(pos.realized_pnl or 0.0)
                ts = pos.closed_at or pos.opened_at
                points.append((ts, running))
            svg = render_roi_curve_svg(points, theme=self.theme)
            out.append(
                ModelEquityCurve(
                    model_id=model_id,
                    points=points,
                    final_equity=running,
                    n_trades=len(ordered),
                    svg=svg,
                )
            )
        return out

    def render(self, data: List[ModelEquityCurve]) -> Markup:
        if not data:
            return self.render_empty("No settled positions yet.")

        sections = []
        for curve in data:
            sign_class = "positive" if curve.final_equity >= 0 else "negative"
            sections.append(
                '<section class="roi-model">'
                f'<h3 class="roi-model__title">{escape(curve.model_id)}</h3>'
                '<div class="roi-model__meta">'
                f'<span class="{sign_class}">'
                f"{curve.final_equity:+.2f}</span> "
                f"over {curve.n_trades} trades"
                "</div>"
                f'<div class="roi-model__chart">{curve.svg}</div>'
                "</section>"
            )

        html = (
            '<div class="widget widget-model-roi-curve" '
            f'data-widget-type="{escape(self.type)}">'
            '<div class="widget__header">Model ROI Curves</div>'
            f'{"".join(sections)}'
            "</div>"
        )
        return Markup(html)
