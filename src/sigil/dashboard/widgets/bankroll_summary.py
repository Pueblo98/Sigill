"""bankroll_summary widget.

Reads the latest BankrollSnapshot for the configured mode (default: paper).
Renders equity, realized PnL, unrealized PnL, ROI vs `BANKROLL_INITIAL`, and
settled-trade counts. Empty state when no snapshot exists yet.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any, ClassVar, Optional, Type

from markupsafe import Markup, escape
from sqlalchemy import desc, select

from sigil.config import config as _root_config
from sigil.dashboard.config import WidgetConfig
from sigil.dashboard.widget import WidgetBase, register_widget
from sigil.models import BankrollSnapshot


class BankrollSummaryConfig(WidgetConfig):
    mode: Optional[str] = None  # default to root config DEFAULT_MODE


@dataclass(frozen=True)
class BankrollSummaryData:
    mode: str
    equity: float
    realized_pnl: float
    unrealized_pnl: float
    roi_pct: float
    settled_trades_total: int
    settled_trades_30d: int
    as_of: datetime


@register_widget("bankroll_summary")
class BankrollSummaryWidget(WidgetBase):
    config_model: ClassVar[Type[WidgetConfig]] = BankrollSummaryConfig

    def __init__(self, config: BankrollSummaryConfig):
        super().__init__(config)
        self._mode: str = config.mode or _root_config.DEFAULT_MODE

    def cache_key(self) -> str:
        return f"{self.type}:{self._mode}"

    async def fetch(self, session: Any) -> Optional[BankrollSummaryData]:
        q = (
            select(BankrollSnapshot)
            .where(BankrollSnapshot.mode == self._mode)
            .order_by(desc(BankrollSnapshot.time))
            .limit(1)
        )
        row = (await session.execute(q)).scalars().first()
        if row is None:
            return None

        initial = float(_root_config.BANKROLL_INITIAL or 0.0)
        equity = float(row.equity)
        roi_pct = ((equity - initial) / initial * 100.0) if initial else 0.0

        return BankrollSummaryData(
            mode=row.mode,
            equity=equity,
            realized_pnl=float(row.realized_pnl_total),
            unrealized_pnl=float(row.unrealized_pnl_total),
            roi_pct=roi_pct,
            settled_trades_total=int(row.settled_trades_total),
            settled_trades_30d=int(row.settled_trades_30d),
            as_of=row.time,
        )

    def render(self, data: Optional[BankrollSummaryData]) -> Markup:
        if data is None:
            return self.render_empty("No bankroll snapshot yet.")

        roi_class = "positive" if data.roi_pct >= 0 else "negative"
        unrl_class = "positive" if data.unrealized_pnl >= 0 else "negative"
        rl_class = "positive" if data.realized_pnl >= 0 else "negative"

        html = (
            '<div class="widget widget-bankroll-summary" '
            f'data-widget-type="{escape(self.type)}">'
            f'<div class="widget__header">Bankroll '
            f'<span class="widget__mode">{escape(data.mode)}</span></div>'
            '<dl class="kv">'
            f'<dt>Equity</dt><dd>${data.equity:,.2f}</dd>'
            f'<dt>ROI</dt><dd class="{roi_class}">{data.roi_pct:+.2f}%</dd>'
            f'<dt>Realized PnL</dt><dd class="{rl_class}">${data.realized_pnl:+,.2f}</dd>'
            f'<dt>Unrealized PnL</dt><dd class="{unrl_class}">${data.unrealized_pnl:+,.2f}</dd>'
            f'<dt>Settled trades (total)</dt><dd>{data.settled_trades_total}</dd>'
            f'<dt>Settled trades (30d)</dt><dd>{data.settled_trades_30d}</dd>'
            "</dl>"
            f'<div class="widget__footer" data-relative-time="{escape(data.as_of.isoformat())}">'
            f"as of {escape(data.as_of.isoformat())}</div>"
            "</div>"
        )
        return Markup(html)
