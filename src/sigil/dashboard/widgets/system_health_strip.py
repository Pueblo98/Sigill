"""system_health_strip widget.

Aggregates SourceHealth (last 24h) + recent ReconciliationObservation rows
and renders three colored dots: ingestion, reconciliation, scheduler.

Status mapping:
  ok       — most recent ingestion check is "ok" or "healthy", last
             reconciliation observation is_match, scheduler heartbeat
             present in the last hour.
  warning  — degraded ingestion (one source non-ok), or reconciliation
             showing a recent mismatch but not yet stuck.
  error    — no ingestion data in 24h, reconciliation stuck >3 mismatches,
             scheduler heartbeat missing.

Scheduler heartbeat: we use the freshest source_health row as a proxy. If
the orchestrator is alive, *something* is reporting in. A real heartbeat
table would be nicer; out of scope for F1 (TODO(lane-F1) above the proxy).
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any, ClassVar, Dict, List, Literal, Optional, Type

from markupsafe import Markup, escape
from sqlalchemy import desc, select

from sigil.dashboard.config import WidgetConfig
from sigil.dashboard.widget import WidgetBase, register_widget
from sigil.models import ReconciliationObservation, SourceHealth


Status = Literal["ok", "warning", "error"]


def _ensure_aware(dt: datetime) -> datetime:
    """SQLite drops timezone info. Treat naive timestamps as UTC."""
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt


class SystemHealthStripConfig(WidgetConfig):
    pass


@dataclass(frozen=True)
class HealthDot:
    label: str
    status: Status
    detail: str


@dataclass(frozen=True)
class SystemHealthData:
    ingestion: HealthDot
    reconciliation: HealthDot
    scheduler: HealthDot


@register_widget("system_health_strip")
class SystemHealthStripWidget(WidgetBase):
    config_model: ClassVar[Type[WidgetConfig]] = SystemHealthStripConfig

    async def fetch(self, session: Any) -> SystemHealthData:
        now = datetime.now(timezone.utc)
        cutoff_24h = now - timedelta(hours=24)
        cutoff_1h = now - timedelta(hours=1)

        sh_rows = (await session.execute(select(SourceHealth))).scalars().all()
        # SQLite (used in tests) returns naive datetimes even when we store
        # aware ones. Normalize and apply the 24h filter in Python.
        sh_rows = [r for r in sh_rows if _ensure_aware(r.check_time) >= cutoff_24h]

        ingestion = self._classify_ingestion(sh_rows)
        scheduler = self._classify_scheduler(sh_rows, cutoff_1h)

        recon_rows = (
            await session.execute(
                select(ReconciliationObservation)
                .order_by(desc(ReconciliationObservation.observed_at))
                .limit(20)
            )
        ).scalars().all()
        reconciliation = self._classify_reconciliation(recon_rows)

        return SystemHealthData(
            ingestion=ingestion,
            reconciliation=reconciliation,
            scheduler=scheduler,
        )

    @staticmethod
    def _classify_ingestion(rows: List[SourceHealth]) -> HealthDot:
        if not rows:
            return HealthDot(label="Ingestion", status="error", detail="no checks in 24h")

        latest_per_source: Dict[str, SourceHealth] = {}
        for r in rows:
            cur = latest_per_source.get(r.source_name)
            if cur is None or _ensure_aware(r.check_time) > _ensure_aware(cur.check_time):
                latest_per_source[r.source_name] = r

        non_ok = [r for r in latest_per_source.values() if r.status not in ("ok", "healthy")]
        if not non_ok:
            return HealthDot(
                label="Ingestion",
                status="ok",
                detail=f"{len(latest_per_source)} sources healthy",
            )
        if len(non_ok) == len(latest_per_source):
            return HealthDot(label="Ingestion", status="error", detail="all sources degraded")
        return HealthDot(
            label="Ingestion",
            status="warning",
            detail=f"{len(non_ok)}/{len(latest_per_source)} sources degraded",
        )

    @staticmethod
    def _classify_scheduler(rows: List[SourceHealth], cutoff_1h: datetime) -> HealthDot:
        recent = [r for r in rows if _ensure_aware(r.check_time) >= cutoff_1h]
        if recent:
            return HealthDot(
                label="Scheduler",
                status="ok",
                detail=f"{len(recent)} checks in last hour",
            )
        return HealthDot(
            label="Scheduler",
            status="error",
            detail="no scheduler activity in last hour",
        )

    @staticmethod
    def _classify_reconciliation(rows: List[ReconciliationObservation]) -> HealthDot:
        if not rows:
            return HealthDot(
                label="Reconciliation",
                status="ok",
                detail="no observations yet",
            )
        latest = rows[0]
        if latest.is_match:
            return HealthDot(
                label="Reconciliation",
                status="ok",
                detail=f"{latest.consecutive_matches} consecutive matches",
            )
        # latest is a mismatch — count recent consecutive mismatches.
        mismatches = 0
        for r in rows:
            if r.is_match:
                break
            mismatches += 1
        if mismatches >= 3:
            return HealthDot(
                label="Reconciliation",
                status="error",
                detail=f"{mismatches} consecutive mismatches",
            )
        return HealthDot(
            label="Reconciliation",
            status="warning",
            detail=f"{mismatches} mismatch(es)",
        )

    def render(self, data: SystemHealthData) -> Markup:
        dots = [data.ingestion, data.reconciliation, data.scheduler]
        dots_html = "".join(
            (
                f'<div class="health-dot health-dot--{escape(d.status)}">'
                f'<span class="health-dot__bullet" aria-hidden="true"></span>'
                f'<span class="health-dot__label">{escape(d.label)}</span>'
                f'<span class="health-dot__detail">{escape(d.detail)}</span>'
                "</div>"
            )
            for d in dots
        )
        html = (
            '<div class="widget widget-system-health-strip" '
            f'data-widget-type="{escape(self.type)}">'
            '<div class="widget__header">System Health</div>'
            f'<div class="health-strip">{dots_html}</div>'
            "</div>"
        )
        return Markup(html)
