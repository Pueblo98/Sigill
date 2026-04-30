"""recent_activity widget.

Combined feed of recent Order rows + recently-settled Position rows. Shows
top-N (default 20) sorted by the relevant timestamp, descending.

Each entry: timestamp, action ("order placed" / "position closed" /
"settlement"), market title.

We treat any Position with status='closed' or status='settled' as
"settlement" (the local settlement handler in Lane A may use either).
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any, ClassVar, List, Optional, Type

from markupsafe import Markup, escape
from pydantic import Field
from sqlalchemy import desc, or_, select

from sigil.dashboard.config import WidgetConfig
from sigil.dashboard.widget import WidgetBase, register_widget
from sigil.models import Market, Order, Position


class RecentActivityConfig(WidgetConfig):
    limit: int = Field(default=20, ge=1, le=200)


@dataclass(frozen=True)
class ActivityEntry:
    when: datetime
    kind: str  # "order" | "settlement"
    action: str  # human label
    market_title: str
    detail: str


@register_widget("recent_activity")
class RecentActivityWidget(WidgetBase):
    config_model: ClassVar[Type[WidgetConfig]] = RecentActivityConfig

    def __init__(self, config: RecentActivityConfig):
        super().__init__(config)
        self._limit = config.limit

    def cache_key(self) -> str:
        return f"{self.type}:limit={self._limit}"

    async def fetch(self, session: Any) -> List[ActivityEntry]:
        order_q = (
            select(Order, Market)
            .join(Market, Market.id == Order.market_id)
            .order_by(desc(Order.created_at))
            .limit(self._limit)
        )
        order_rows = (await session.execute(order_q)).all()

        pos_q = (
            select(Position, Market)
            .join(Market, Market.id == Position.market_id)
            .where(or_(Position.status == "closed", Position.status == "settled"))
            .order_by(desc(Position.closed_at))
            .limit(self._limit)
        )
        pos_rows = (await session.execute(pos_q)).all()

        entries: List[ActivityEntry] = []
        for order, mkt in order_rows:
            if order.created_at is None:
                continue
            entries.append(
                ActivityEntry(
                    when=order.created_at,
                    kind="order",
                    action="order placed",
                    market_title=mkt.title,
                    detail=(
                        f"{order.side} {order.outcome} qty={int(order.quantity)} @ "
                        f"{float(order.price):.3f} ({order.status})"
                    ),
                )
            )
        for pos, mkt in pos_rows:
            ts = pos.closed_at or pos.opened_at
            if ts is None:
                continue
            action = "position closed" if pos.status == "closed" else "settlement"
            entries.append(
                ActivityEntry(
                    when=ts,
                    kind="settlement",
                    action=action,
                    market_title=mkt.title,
                    detail=(
                        f"{pos.outcome} qty={int(pos.quantity)} "
                        f"realized={float(pos.realized_pnl):+.2f}"
                    ),
                )
            )

        entries.sort(key=lambda e: e.when, reverse=True)
        return entries[: self._limit]

    def render(self, data: List[ActivityEntry]) -> Markup:
        if not data:
            return self.render_empty("No recent activity.")

        items_html = "".join(
            (
                f'<li class="activity-item activity-item--{escape(e.kind)}">'
                f'<span class="activity-item__when" data-relative-time="{escape(e.when.isoformat())}">'
                f"{escape(e.when.isoformat())}</span>"
                f'<span class="activity-item__action">{escape(e.action)}</span>'
                f'<span class="activity-item__market">{escape(e.market_title)}</span>'
                f'<span class="activity-item__detail">{escape(e.detail)}</span>'
                "</li>"
            )
            for e in data
        )
        html = (
            '<div class="widget widget-recent-activity" '
            f'data-widget-type="{escape(self.type)}">'
            '<div class="widget__header">Recent Activity</div>'
            f'<ol class="activity-feed">{items_html}</ol>'
            "</div>"
        )
        return Markup(html)
