"""model_calibration widget.

Calibration curve(s) for top-N models (default 1, configurable) over
settled markets. Renders an SVG calibration plot via
``charts.render_calibration_curve_svg`` plus a small bin-by-bin table.

Empty state when fewer than 30 settled predictions exist for any model.

The "top-N" selection here is by sample count (n_predictions): more data is
better calibrated by default. Users who want by-Brier can wire it through
config later.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, ClassVar, Dict, List, Type
from uuid import UUID

from markupsafe import Markup, escape
from pydantic import Field
from sqlalchemy import select

from sigil.backtesting.metrics import calibration_curve, prediction_outcomes_from_orm
from sigil.dashboard.config import WidgetConfig
from sigil.dashboard.widget import WidgetBase, register_widget
from sigil.dashboard.widgets.charts import render_calibration_curve_svg
from sigil.models import Market, Prediction


_MIN_PREDICTIONS = 30


class ModelCalibrationConfig(WidgetConfig):
    top_n: int = Field(default=1, ge=1, le=10)
    n_bins: int = Field(default=10, ge=2, le=50)


@dataclass(frozen=True)
class CalibrationModelView:
    model_id: str
    n_predictions: int
    bins: List[tuple]  # list of (mean_predicted, observed)
    svg: str


@register_widget("model_calibration")
class ModelCalibrationWidget(WidgetBase):
    config_model: ClassVar[Type[WidgetConfig]] = ModelCalibrationConfig

    def __init__(self, config: ModelCalibrationConfig):
        super().__init__(config)
        self._top_n = config.top_n
        self._n_bins = config.n_bins

    def cache_key(self) -> str:
        return f"{self.type}:top_n={self._top_n}:n_bins={self._n_bins}"

    async def fetch(self, session: Any) -> List[CalibrationModelView]:
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

        per_model: Dict[str, List[Prediction]] = {}
        for p in preds:
            per_model.setdefault(p.model_id, []).append(p)

        # Drop models that don't meet the minimum.
        eligible = {
            m: ps for m, ps in per_model.items()
            if len(prediction_outcomes_from_orm(ps, markets_by_id)) >= _MIN_PREDICTIONS
        }
        if not eligible:
            return []

        # Top-N by n_predictions (descending), tie-break by model_id.
        ranked = sorted(
            eligible.items(),
            key=lambda kv: (
                -len(prediction_outcomes_from_orm(kv[1], markets_by_id)),
                kv[0],
            ),
        )[: self._top_n]

        out: List[CalibrationModelView] = []
        for model_id, model_preds in ranked:
            outcomes = prediction_outcomes_from_orm(model_preds, markets_by_id)
            probs = [o.predicted_prob for o in outcomes]
            outs = [o.outcome for o in outcomes]
            mean_pred, observed = calibration_curve(probs, outs, n_bins=self._n_bins)
            svg = render_calibration_curve_svg(mean_pred, observed)
            out.append(
                CalibrationModelView(
                    model_id=model_id,
                    n_predictions=len(outcomes),
                    bins=list(zip(mean_pred, observed)),
                    svg=svg,
                )
            )
        return out

    def render(self, data: List[CalibrationModelView]) -> Markup:
        if not data:
            return self.render_empty("Need 30+ settled predictions to calibrate.")

        sections = []
        for view in data:
            bin_rows = "".join(
                (
                    "<tr>"
                    f"<td>{mean_pred:.3f}</td>"
                    f"<td>{observed:.3f}</td>"
                    "</tr>"
                )
                for mean_pred, observed in view.bins
            )
            sections.append(
                '<section class="calibration-model">'
                f'<h3 class="calibration-model__title">{escape(view.model_id)}</h3>'
                f'<div class="calibration-model__count">'
                f"n_predictions = {view.n_predictions}</div>"
                f'<div class="calibration-model__chart">{view.svg}</div>'
                '<table class="widget__table calibration-model__bins">'
                "<thead><tr><th>mean predicted</th><th>observed</th></tr></thead>"
                f"<tbody>{bin_rows}</tbody>"
                "</table>"
                "</section>"
            )

        html = (
            '<div class="widget widget-model-calibration" '
            f'data-widget-type="{escape(self.type)}">'
            '<div class="widget__header">Model Calibration</div>'
            f'{"".join(sections)}'
            "</div>"
        )
        return Markup(html)
