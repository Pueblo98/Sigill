"""market_list widget.

Open Market rows joined with their latest MarketPrice. Filterable by
min_edge (computed from latest Prediction if available) and platform.
Sortable: edge_desc | volume_desc. Default top-N = 50.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any, ClassVar, List, Literal, Optional, Type
from uuid import UUID

from markupsafe import Markup, escape
from pydantic import Field, model_validator
from sqlalchemy import desc, select

from sigil.dashboard.config import WidgetConfig
from sigil.dashboard.widget import WidgetBase, register_widget
from sigil.models import Market, MarketPrice, Prediction


SortMode = Literal["edge_desc", "volume_desc"]


class MarketListConfig(WidgetConfig):
    limit: int = Field(default=50, ge=1, le=500)
    min_edge: Optional[float] = None
    platform: Optional[str] = None
    sort: SortMode = "edge_desc"

    @model_validator(mode="before")
    @classmethod
    def _hoist_filters(cls, values: Any) -> Any:
        if isinstance(values, dict) and "filters" in values:
            filters = values.pop("filters") or {}
            if isinstance(filters, dict):
                for k, v in filters.items():
                    values.setdefault(k, v)
        return values


@dataclass(frozen=True)
class MarketRow:
    market_id: str
    external_id: str
    platform: str
    title: str
    bid: Optional[float]
    ask: Optional[float]
    last_price: Optional[float]
    volume_24h: Optional[float]
    edge: Optional[float]
    last_price_at: Optional[datetime]


@register_widget("market_list")
class MarketListWidget(WidgetBase):
    config_model: ClassVar[Type[WidgetConfig]] = MarketListConfig

    def __init__(self, config: MarketListConfig):
        super().__init__(config)
        self._limit = config.limit
        self._min_edge = config.min_edge
        self._platform = config.platform
        self._sort: SortMode = config.sort

    def cache_key(self) -> str:
        return (
            f"{self.type}:limit={self._limit}:min_edge={self._min_edge}:"
            f"platform={self._platform}:sort={self._sort}"
        )

    async def fetch(self, session: Any) -> List[MarketRow]:
        q = select(Market).where(Market.status == "open")
        if self._platform:
            q = q.where(Market.platform == self._platform)
        # Pull a wider slice than `limit` so post-filter sort still has data.
        q = q.limit(max(self._limit * 4, 200))
        markets = (await session.execute(q)).scalars().all()
        if not markets:
            return []

        # Latest price per market.
        prices_by_market: dict[UUID, MarketPrice] = {}
        for m in markets:
            p_row = (
                await session.execute(
                    select(MarketPrice)
                    .where(MarketPrice.market_id == m.id)
                    .order_by(desc(MarketPrice.time))
                    .limit(1)
                )
            ).scalars().first()
            if p_row is not None:
                prices_by_market[m.id] = p_row

        # Latest edge per market (Prediction.edge of most recent prediction).
        edges_by_market: dict[UUID, Optional[float]] = {}
        for m in markets:
            p_row = (
                await session.execute(
                    select(Prediction)
                    .where(Prediction.market_id == m.id)
                    .order_by(desc(Prediction.created_at))
                    .limit(1)
                )
            ).scalars().first()
            edges_by_market[m.id] = (
                float(p_row.edge) if (p_row is not None and p_row.edge is not None) else None
            )

        out: List[MarketRow] = []
        for m in markets:
            price = prices_by_market.get(m.id)
            edge = edges_by_market.get(m.id)
            if self._min_edge is not None:
                if edge is None or edge < self._min_edge:
                    continue
            out.append(
                MarketRow(
                    market_id=str(m.id),
                    external_id=m.external_id,
                    platform=m.platform,
                    title=m.title,
                    bid=float(price.bid) if price and price.bid is not None else None,
                    ask=float(price.ask) if price and price.ask is not None else None,
                    last_price=float(price.last_price)
                    if price and price.last_price is not None
                    else None,
                    volume_24h=float(price.volume_24h)
                    if price and price.volume_24h is not None
                    else None,
                    edge=edge,
                    last_price_at=price.time if price else None,
                )
            )

        if self._sort == "volume_desc":
            out.sort(key=lambda r: (r.volume_24h or 0.0), reverse=True)
        else:
            out.sort(key=lambda r: (r.edge if r.edge is not None else -1.0), reverse=True)

        return out[: self._limit]

    def render(self, data: List[MarketRow]) -> Markup:
        if not data:
            return self.render_empty("No open markets match the current filters.")

        rows_html = "".join(
            (
                "<tr>"
                f"<td>{escape(r.platform)}</td>"
                f"<td>{escape(r.title)}</td>"
                f"<td>{('-' if r.bid is None else f'{r.bid:.3f}')}</td>"
                f"<td>{('-' if r.ask is None else f'{r.ask:.3f}')}</td>"
                f"<td>{('-' if r.last_price is None else f'{r.last_price:.3f}')}</td>"
                f"<td>{('-' if r.volume_24h is None else f'{r.volume_24h:,.0f}')}</td>"
                f"<td>{('-' if r.edge is None else f'{r.edge:+.3f}')}</td>"
                "</tr>"
            )
            for r in data
        )
        html = (
            '<div class="widget widget-market-list" '
            f'data-widget-type="{escape(self.type)}">'
            '<div class="widget__header">Markets</div>'
            '<table class="widget__table">'
            "<thead><tr>"
            "<th>Platform</th><th>Market</th><th>Bid</th><th>Ask</th>"
            "<th>Last</th><th>Vol 24h</th><th>Edge</th>"
            "</tr></thead>"
            f"<tbody>{rows_html}</tbody>"
            "</table>"
            "</div>"
        )
        return Markup(html)
