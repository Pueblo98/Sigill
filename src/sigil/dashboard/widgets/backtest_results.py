"""backtest_results widget.

Renders the most recent persisted backtest result.

The ``backtest_results`` table is defined in ``sigil.models.BacktestResult``
and populated by ``sigil.backtesting.persistence.persist_backtest_result``
(TODO-8). The widget keeps an ``OperationalError`` fallback so older
deploys that haven't run the migration still render the empty state instead
of throwing 500s.

The render contract degrades gracefully — NULL columns (Brier, log loss,
calibration error) are skipped rather than rendered as "n/a".
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any, ClassVar, Optional, Type

from markupsafe import Markup, escape
from sqlalchemy import select
from sqlalchemy.exc import OperationalError, ProgrammingError

from sigil.dashboard.config import WidgetConfig
from sigil.dashboard.widget import WidgetBase, register_widget
from sigil.models import BacktestResult


class BacktestResultsConfig(WidgetConfig):
    pass


@dataclass(frozen=True)
class BacktestResultRow:
    name: Optional[str]
    created_at: Optional[datetime]
    initial_capital: Optional[float]
    final_equity: Optional[float]
    roi: Optional[float]
    sharpe: Optional[float]
    max_drawdown: Optional[float]
    n_trades: Optional[int]
    brier: Optional[float]
    log_loss: Optional[float]
    calibration_error: Optional[float]


def _coerce_float(v: Any) -> Optional[float]:
    if v is None:
        return None
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def _coerce_int(v: Any) -> Optional[int]:
    if v is None:
        return None
    try:
        return int(v)
    except (TypeError, ValueError):
        return None


def _coerce_datetime(v: Any) -> Optional[datetime]:
    """SQLite returns TIMESTAMPs as ISO strings via raw SQL — parse them
    back so callers can call ``.isoformat()`` uniformly. Postgres already
    returns datetime objects, in which case this is a no-op.
    """
    if v is None:
        return None
    if isinstance(v, datetime):
        return v
    if isinstance(v, str):
        try:
            return datetime.fromisoformat(v.replace("Z", "+00:00"))
        except ValueError:
            return None
    return None


@register_widget("backtest_results")
class BacktestResultsWidget(WidgetBase):
    config_model: ClassVar[Type[WidgetConfig]] = BacktestResultsConfig

    async def fetch(self, session: Any) -> Optional[BacktestResultRow]:
        try:
            result = await session.execute(
                select(BacktestResult)
                .order_by(BacktestResult.created_at.desc())
                .limit(1)
            )
            row = result.scalar_one_or_none()
        except (OperationalError, ProgrammingError):
            # Migration hasn't been run on this deploy yet. Empty state
            # rather than 500.
            return None

        if row is None:
            return None
        return BacktestResultRow(
            name=row.name,
            created_at=_coerce_datetime(row.created_at),
            initial_capital=_coerce_float(row.initial_capital),
            final_equity=_coerce_float(row.final_equity),
            roi=_coerce_float(row.roi),
            sharpe=_coerce_float(row.sharpe),
            max_drawdown=_coerce_float(row.max_drawdown),
            n_trades=_coerce_int(row.n_trades),
            brier=_coerce_float(row.brier),
            log_loss=_coerce_float(row.log_loss),
            calibration_error=_coerce_float(row.calibration_error),
        )

    def render(self, data: Optional[BacktestResultRow]) -> Markup:
        if data is None:
            return self.render_empty("No backtest results yet.")

        def _row(label: str, value: Optional[float], fmt: str = "{:.4f}") -> str:
            if value is None:
                return ""
            try:
                rendered = fmt.format(value)
            except (TypeError, ValueError):
                rendered = str(value)
            return f"<dt>{escape(label)}</dt><dd>{escape(rendered)}</dd>"

        roi_class = ""
        if data.roi is not None:
            roi_class = "positive" if data.roi >= 0 else "negative"

        title = escape(data.name) if data.name else "latest"
        when_html = ""
        if data.created_at is not None:
            when_html = (
                f'<div class="widget__footer" '
                f'data-relative-time="{escape(data.created_at.isoformat())}">'
                f"as of {escape(data.created_at.isoformat())}</div>"
            )

        kv_rows = []
        if data.roi is not None:
            kv_rows.append(
                f'<dt>ROI</dt><dd class="{roi_class}">{data.roi * 100:+.2f}%</dd>'
            )
        kv_rows.append(_row("Final equity", data.final_equity, "{:,.2f}"))
        kv_rows.append(_row("Initial capital", data.initial_capital, "{:,.2f}"))
        kv_rows.append(_row("Sharpe (eq.)", data.sharpe))
        kv_rows.append(_row("Max drawdown", data.max_drawdown, "{:.4f}"))
        if data.n_trades is not None:
            kv_rows.append(f"<dt>Trades</dt><dd>{data.n_trades}</dd>")
        kv_rows.append(_row("Brier", data.brier))
        kv_rows.append(_row("Log loss", data.log_loss))
        kv_rows.append(_row("Calibration err.", data.calibration_error))

        html = (
            '<div class="widget widget-backtest-results" '
            f'data-widget-type="{escape(self.type)}">'
            f'<div class="widget__header">Backtest <span class="widget__mode">'
            f"{title}</span></div>"
            f'<dl class="kv">{"".join(r for r in kv_rows if r)}</dl>'
            f"{when_html}"
            "</div>"
        )
        return Markup(html)
