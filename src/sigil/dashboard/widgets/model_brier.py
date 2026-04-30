"""model_brier widget.

Computes Brier scores per ``model_id`` over rolling 30-day and 90-day
windows using settled markets (``Market.settlement_value IS NOT NULL``).
Renders as a table — model_id, n (30d), brier_30d, n (90d), brier_90d.
Empty state when no settled predictions exist.

Reuses :mod:`sigil.backtesting.metrics` (decision: do not reimplement Brier).
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any, ClassVar, Dict, List, Type
from uuid import UUID

from markupsafe import Markup, escape
from sqlalchemy import select

from sigil.backtesting.metrics import brier_score, prediction_outcomes_from_orm
from sigil.dashboard.config import WidgetConfig
from sigil.dashboard.widget import WidgetBase, register_widget
from sigil.models import Market, Prediction


def _ensure_aware(dt: datetime) -> datetime:
    """SQLite drops timezone info — promote naive timestamps to UTC."""
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt


class ModelBrierConfig(WidgetConfig):
    pass


@dataclass(frozen=True)
class ModelBrierRow:
    model_id: str
    n_30d: int
    brier_30d: float
    n_90d: int
    brier_90d: float


@register_widget("model_brier")
class ModelBrierWidget(WidgetBase):
    config_model: ClassVar[Type[WidgetConfig]] = ModelBrierConfig

    async def fetch(self, session: Any) -> List[ModelBrierRow]:
        # Pull every settled market once, then index by id. Settlement counts
        # are tiny relative to the predictions stream, and the join-side
        # filter keeps the prediction set bounded too.
        markets = (
            await session.execute(
                select(Market).where(Market.settlement_value.is_not(None))
            )
        ).scalars().all()
        if not markets:
            return []
        markets_by_id: Dict[UUID, Market] = {m.id: m for m in markets}

        preds = (
            await session.execute(
                select(Prediction).where(Prediction.market_id.in_(markets_by_id.keys()))
            )
        ).scalars().all()
        if not preds:
            return []

        now = datetime.now(timezone.utc)
        cutoff_30 = now - timedelta(days=30)
        cutoff_90 = now - timedelta(days=90)

        per_model_30: Dict[str, List[Prediction]] = {}
        per_model_90: Dict[str, List[Prediction]] = {}
        for p in preds:
            ts = _ensure_aware(p.created_at) if p.created_at is not None else now
            if ts >= cutoff_90:
                per_model_90.setdefault(p.model_id, []).append(p)
                if ts >= cutoff_30:
                    per_model_30.setdefault(p.model_id, []).append(p)

        out: List[ModelBrierRow] = []
        all_models = sorted(set(per_model_90.keys()) | set(per_model_30.keys()))
        for model_id in all_models:
            outcomes_30 = prediction_outcomes_from_orm(
                per_model_30.get(model_id, []), markets_by_id
            )
            outcomes_90 = prediction_outcomes_from_orm(
                per_model_90.get(model_id, []), markets_by_id
            )
            n30 = len(outcomes_30)
            n90 = len(outcomes_90)
            b30 = (
                brier_score(
                    [o.predicted_prob for o in outcomes_30],
                    [o.outcome for o in outcomes_30],
                )
                if n30
                else float("nan")
            )
            b90 = (
                brier_score(
                    [o.predicted_prob for o in outcomes_90],
                    [o.outcome for o in outcomes_90],
                )
                if n90
                else float("nan")
            )
            out.append(
                ModelBrierRow(
                    model_id=model_id,
                    n_30d=n30,
                    brier_30d=b30,
                    n_90d=n90,
                    brier_90d=b90,
                )
            )
        # Sort: lower 30d Brier first, NaNs last.
        out.sort(
            key=lambda r: (r.brier_30d != r.brier_30d, r.brier_30d, r.model_id)
        )
        return out

    def render(self, data: List[ModelBrierRow]) -> Markup:
        if not data:
            return self.render_empty("No settled predictions yet.")

        def _fmt(v: float, n: int) -> str:
            if n == 0 or v != v:  # NaN check
                return "-"
            return f"{v:.4f}"

        rows_html = "".join(
            (
                "<tr>"
                f"<td>{escape(r.model_id)}</td>"
                f"<td>{r.n_30d}</td>"
                f"<td>{_fmt(r.brier_30d, r.n_30d)}</td>"
                f"<td>{r.n_90d}</td>"
                f"<td>{_fmt(r.brier_90d, r.n_90d)}</td>"
                "</tr>"
            )
            for r in data
        )
        html = (
            '<div class="widget widget-model-brier" '
            f'data-widget-type="{escape(self.type)}">'
            '<div class="widget__header">Model Brier (rolling)</div>'
            '<table class="widget__table">'
            "<thead><tr>"
            "<th>Model</th><th>n (30d)</th><th>Brier 30d</th>"
            "<th>n (90d)</th><th>Brier 90d</th>"
            "</tr></thead>"
            f"<tbody>{rows_html}</tbody>"
            "</table>"
            "</div>"
        )
        return Markup(html)
