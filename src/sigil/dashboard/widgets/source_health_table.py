"""source_health_table widget.

Aggregates ``SourceHealth`` checks over the last 24h, one row per
``source_name``: latest status, error count, p50 / p95 latency, last-checked
timestamp. Color-coded via the standard ``positive`` / ``negative`` classes
that the dashboard CSS already understands. Sort is alphabetical by source
name to keep the table layout stable across refreshes.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any, ClassVar, Dict, List, Optional, Type

from markupsafe import Markup, escape
from sqlalchemy import select

from sigil.dashboard.config import WidgetConfig
from sigil.dashboard.widget import WidgetBase, register_widget
from sigil.models import SourceHealth


def _ensure_aware(dt: datetime) -> datetime:
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt


def _percentile(values: List[int], pct: float) -> Optional[float]:
    if not values:
        return None
    s = sorted(values)
    if len(s) == 1:
        return float(s[0])
    # Linear interpolation between closest ranks.
    rank = (pct / 100.0) * (len(s) - 1)
    lower = int(rank)
    upper = min(lower + 1, len(s) - 1)
    weight = rank - lower
    return s[lower] * (1.0 - weight) + s[upper] * weight


class SourceHealthTableConfig(WidgetConfig):
    pass


@dataclass(frozen=True)
class SourceHealthRow:
    source_name: str
    latest_status: str
    error_count_24h: int
    p50_latency_ms: Optional[float]
    p95_latency_ms: Optional[float]
    last_checked: datetime


@register_widget("source_health_table")
class SourceHealthTableWidget(WidgetBase):
    config_model: ClassVar[Type[WidgetConfig]] = SourceHealthTableConfig

    async def fetch(self, session: Any) -> List[SourceHealthRow]:
        rows = (await session.execute(select(SourceHealth))).scalars().all()
        if not rows:
            return []

        cutoff = datetime.now(timezone.utc) - timedelta(hours=24)
        recent = [r for r in rows if _ensure_aware(r.check_time) >= cutoff]
        if not recent:
            return []

        per_source: Dict[str, List[SourceHealth]] = {}
        for r in recent:
            per_source.setdefault(r.source_name, []).append(r)

        out: List[SourceHealthRow] = []
        for name in sorted(per_source.keys()):
            checks = per_source[name]
            latest = max(checks, key=lambda c: _ensure_aware(c.check_time))
            error_count = sum(1 for c in checks if c.error_message)
            latencies = [int(c.latency_ms) for c in checks if c.latency_ms is not None]
            out.append(
                SourceHealthRow(
                    source_name=name,
                    latest_status=latest.status,
                    error_count_24h=error_count,
                    p50_latency_ms=_percentile(latencies, 50.0),
                    p95_latency_ms=_percentile(latencies, 95.0),
                    last_checked=latest.check_time,
                )
            )
        return out

    def render(self, data: List[SourceHealthRow]) -> Markup:
        if not data:
            return self.render_empty("No source health checks in 24h.")

        def _status_class(status: str) -> str:
            if status in ("ok", "healthy"):
                return "positive"
            if status in ("degraded", "warning"):
                return "warning"
            return "negative"

        def _fmt_latency(v: Optional[float]) -> str:
            return "-" if v is None else f"{v:.0f}"

        rows_html = "".join(
            (
                "<tr>"
                f"<td>{escape(r.source_name)}</td>"
                f'<td class="{_status_class(r.latest_status)}">'
                f"{escape(r.latest_status)}</td>"
                f"<td>{r.error_count_24h}</td>"
                f"<td>{_fmt_latency(r.p50_latency_ms)}</td>"
                f"<td>{_fmt_latency(r.p95_latency_ms)}</td>"
                f'<td data-relative-time="{escape(r.last_checked.isoformat())}">'
                f"{escape(r.last_checked.isoformat())}</td>"
                "</tr>"
            )
            for r in data
        )
        html = (
            '<div class="widget widget-source-health-table" '
            f'data-widget-type="{escape(self.type)}">'
            '<div class="widget__header">Source Health (24h)</div>'
            '<table class="widget__table">'
            "<thead><tr>"
            "<th>Source</th><th>Status</th><th>Errors 24h</th>"
            "<th>p50 ms</th><th>p95 ms</th><th>Last check</th>"
            "</tr></thead>"
            f"<tbody>{rows_html}</tbody>"
            "</table>"
            "</div>"
        )
        return Markup(html)
