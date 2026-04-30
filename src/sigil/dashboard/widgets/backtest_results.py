"""backtest_results widget.

Renders the most recent persisted backtest result.

KNOWN SCHEMA GAP (as of phase 5 lane F2): there is no ``BacktestResult`` ORM
table. Lane D's :class:`sigil.backtesting.engine.Backtester` returns an
in-memory result and nothing currently writes it to the database. This
widget queries a *hypothetical* ``backtest_results`` table directly via raw
SQL so we don't need an ORM model. When the table is absent — the common
case today — SQLAlchemy raises ``OperationalError`` (SQLite reports
``no such table`` and Postgres reports ``relation does not exist``); we
treat that as the empty state. The widget will start producing real output
the day a future lane lands the table + persistence shim.

Expected schema (whatever lane lands it should match these column names):

    id                TEXT/UUID PRIMARY KEY
    name              TEXT  -- human label
    created_at        TIMESTAMP
    initial_capital   NUMERIC
    final_equity      NUMERIC
    roi               NUMERIC
    sharpe            NUMERIC
    max_drawdown      NUMERIC
    n_trades          INTEGER
    brier             NUMERIC NULL
    log_loss          NUMERIC NULL
    calibration_error NUMERIC NULL

The render contract degrades gracefully — unknown columns are skipped.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any, ClassVar, Mapping, Optional, Type

from markupsafe import Markup, escape
from sqlalchemy import text
from sqlalchemy.exc import OperationalError, ProgrammingError

from sigil.dashboard.config import WidgetConfig
from sigil.dashboard.widget import WidgetBase, register_widget


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
                text(
                    "SELECT * FROM backtest_results "
                    "ORDER BY created_at DESC LIMIT 1"
                )
            )
            row = result.mappings().first()
        except (OperationalError, ProgrammingError):
            # Table doesn't exist yet — schema gap documented above. Treat
            # as empty rather than blowing up the dashboard.
            return None

        if row is None:
            return None
        return self._coerce_row(row)

    @staticmethod
    def _coerce_row(row: Mapping[str, Any]) -> BacktestResultRow:
        return BacktestResultRow(
            name=row.get("name"),
            created_at=_coerce_datetime(row.get("created_at")),
            initial_capital=_coerce_float(row.get("initial_capital")),
            final_equity=_coerce_float(row.get("final_equity")),
            roi=_coerce_float(row.get("roi")),
            sharpe=_coerce_float(row.get("sharpe")),
            max_drawdown=_coerce_float(row.get("max_drawdown")),
            n_trades=_coerce_int(row.get("n_trades")),
            brier=_coerce_float(row.get("brier")),
            log_loss=_coerce_float(row.get("log_loss")),
            calibration_error=_coerce_float(row.get("calibration_error")),
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
