"""open_positions widget.

Position rows where status='open' AND mode=DEFAULT_MODE, joined with Market.
Renders a table: market, outcome, qty, avg_entry, current_price, unrealized
PnL.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any, ClassVar, List, Optional, Type

from markupsafe import Markup, escape
from sqlalchemy import desc, select

from sigil.config import config as _root_config
from sigil.dashboard.config import WidgetConfig
from sigil.dashboard.widget import WidgetBase, register_widget
from sigil.models import Market, Position


class OpenPositionsConfig(WidgetConfig):
    mode: Optional[str] = None  # falls back to root DEFAULT_MODE


@dataclass(frozen=True)
class PositionRow:
    market_title: str
    platform: str
    outcome: str
    quantity: int
    avg_entry_price: float
    current_price: Optional[float]
    unrealized_pnl: Optional[float]
    opened_at: Optional[datetime]


@register_widget("open_positions")
class OpenPositionsWidget(WidgetBase):
    config_model: ClassVar[Type[WidgetConfig]] = OpenPositionsConfig

    def __init__(self, config: OpenPositionsConfig):
        super().__init__(config)
        self._mode: str = config.mode or _root_config.DEFAULT_MODE

    def cache_key(self) -> str:
        return f"{self.type}:{self._mode}"

    async def fetch(self, session: Any) -> List[PositionRow]:
        q = (
            select(Position, Market)
            .join(Market, Market.id == Position.market_id)
            .where(Position.status == "open", Position.mode == self._mode)
            .order_by(desc(Position.opened_at))
        )
        rows = (await session.execute(q)).all()
        return [
            PositionRow(
                market_title=mkt.title,
                platform=pos.platform,
                outcome=pos.outcome,
                quantity=int(pos.quantity),
                avg_entry_price=float(pos.avg_entry_price),
                current_price=float(pos.current_price)
                if pos.current_price is not None
                else None,
                unrealized_pnl=float(pos.unrealized_pnl)
                if pos.unrealized_pnl is not None
                else None,
                opened_at=pos.opened_at,
            )
            for pos, mkt in rows
        ]

    def render(self, data: List[PositionRow]) -> Markup:
        if not data:
            return self.render_empty("No open positions.")

        rows_html = "".join(
            (
                "<tr>"
                f"<td>{escape(r.platform)}</td>"
                f"<td>{escape(r.market_title)}</td>"
                f"<td>{escape(r.outcome)}</td>"
                f"<td>{r.quantity}</td>"
                f"<td>{r.avg_entry_price:.3f}</td>"
                f"<td>{('-' if r.current_price is None else f'{r.current_price:.3f}')}</td>"
                + (
                    "<td>-</td>"
                    if r.unrealized_pnl is None
                    else (
                        f'<td class="{"positive" if r.unrealized_pnl >= 0 else "negative"}">'
                        f"{r.unrealized_pnl:+.2f}</td>"
                    )
                )
                + "</tr>"
            )
            for r in data
        )
        html = (
            '<div class="widget widget-open-positions" '
            f'data-widget-type="{escape(self.type)}">'
            f'<div class="widget__header">Open Positions <span class="widget__mode">'
            f"{escape(self._mode)}</span></div>"
            '<table class="widget__table">'
            "<thead><tr>"
            "<th>Platform</th><th>Market</th><th>Outcome</th><th>Qty</th>"
            "<th>Avg entry</th><th>Current</th><th>Unrealized PnL</th>"
            "</tr></thead>"
            f"<tbody>{rows_html}</tbody>"
            "</table>"
            "</div>"
        )
        return Markup(html)
