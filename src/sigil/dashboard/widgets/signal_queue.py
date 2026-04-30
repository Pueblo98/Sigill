"""signal_queue widget.

Recent Prediction rows where edge >= filter.min_edge (default 0.05),
sorted by created_at DESC, top-N (default 5). Joins Market for the title.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any, ClassVar, Dict, List, Optional, Type

from markupsafe import Markup, escape
from pydantic import Field, model_validator
from sqlalchemy import desc, select

from sigil.dashboard.config import WidgetConfig
from sigil.dashboard.widget import WidgetBase, register_widget
from sigil.models import Market, Prediction


class SignalQueueConfig(WidgetConfig):
    limit: int = Field(default=5, ge=1, le=200)
    min_edge: float = Field(default=0.05, ge=0.0, le=1.0)

    @model_validator(mode="before")
    @classmethod
    def _hoist_filters(cls, values: Any) -> Any:
        # Allow YAML to nest under `filters: { min_edge: ... }` like the plan
        # example does — flatten into the top-level config so callers can also
        # set min_edge directly.
        if isinstance(values, dict) and "filters" in values:
            filters = values.pop("filters") or {}
            if isinstance(filters, dict):
                for k, v in filters.items():
                    values.setdefault(k, v)
        return values


@dataclass(frozen=True)
class SignalRow:
    market_title: str
    market_id: str
    model_id: str
    predicted_prob: float
    market_price: Optional[float]
    edge: Optional[float]
    created_at: datetime


@register_widget("signal_queue")
class SignalQueueWidget(WidgetBase):
    config_model: ClassVar[Type[WidgetConfig]] = SignalQueueConfig

    def __init__(self, config: SignalQueueConfig):
        super().__init__(config)
        self._limit = config.limit
        self._min_edge = config.min_edge

    def cache_key(self) -> str:
        return f"{self.type}:limit={self._limit}:min_edge={self._min_edge}"

    async def fetch(self, session: Any) -> List[SignalRow]:
        q = (
            select(Prediction, Market)
            .join(Market, Market.id == Prediction.market_id)
            .where(Prediction.edge >= self._min_edge)
            .order_by(desc(Prediction.created_at))
            .limit(self._limit)
        )
        rows = (await session.execute(q)).all()
        return [
            SignalRow(
                market_title=mkt.title,
                market_id=str(mkt.id),
                model_id=pred.model_id,
                predicted_prob=float(pred.predicted_prob),
                market_price=float(pred.market_price_at_prediction)
                if pred.market_price_at_prediction is not None
                else None,
                edge=float(pred.edge) if pred.edge is not None else None,
                created_at=pred.created_at,
            )
            for pred, mkt in rows
        ]

    def render(self, data: List[SignalRow]) -> Markup:
        if not data:
            return self.render_empty("No signals above edge threshold.")

        rows_html = "".join(
            (
                "<tr>"
                f"<td>{escape(r.market_title)}</td>"
                f"<td>{escape(r.model_id)}</td>"
                f"<td>{r.predicted_prob:.3f}</td>"
                f"<td>{('-' if r.market_price is None else f'{r.market_price:.3f}')}</td>"
                f'<td class="positive">{("-" if r.edge is None else f"{r.edge:+.3f}")}</td>'
                f'<td data-relative-time="{escape(r.created_at.isoformat())}">'
                f"{escape(r.created_at.isoformat())}</td>"
                "</tr>"
            )
            for r in data
        )
        html = (
            '<div class="widget widget-signal-queue" '
            f'data-widget-type="{escape(self.type)}">'
            '<div class="widget__header">Signal Queue</div>'
            '<table class="widget__table">'
            "<thead><tr>"
            "<th>Market</th><th>Model</th><th>p</th><th>price</th><th>edge</th><th>when</th>"
            "</tr></thead>"
            f"<tbody>{rows_html}</tbody>"
            "</table>"
            "</div>"
        )
        return Markup(html)
