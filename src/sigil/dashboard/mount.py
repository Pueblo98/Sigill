"""FastAPI mounting for the Jinja2 dashboard surface.

This module keeps the dashboard's HTTP wiring out of `sigil/api/server.py` so
the existing JSON API stays the file's main concern. Call `mount_dashboard(app)`
once during app construction; call `start_dashboard(app, scheduler, ...)` from
the lifespan handler when DASHBOARD_ENABLED is true.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from markupsafe import Markup

from sigil.dashboard.cache import WidgetCache
from sigil.dashboard.config import DashboardConfig, Page
from sigil.dashboard.loader import build_widget_instances, load_dashboard
from sigil.dashboard.refresh import RefreshOrchestrator
from sigil.dashboard.widget import WidgetBase

logger = logging.getLogger(__name__)


_PACKAGE_ROOT = Path(__file__).resolve().parent
TEMPLATES_DIR = _PACKAGE_ROOT / "templates"
STATIC_DIR = _PACKAGE_ROOT / "static"


# State stashed on `app.state.dashboard` so tests can poke at it.
class DashboardState:
    def __init__(
        self,
        *,
        config: DashboardConfig,
        widgets: List[WidgetBase],
        cache: WidgetCache,
        templates: Jinja2Templates,
    ) -> None:
        self.config = config
        self.widgets = widgets
        self.cache = cache
        self.templates = templates
        self.orchestrator: Optional[RefreshOrchestrator] = None


def mount_dashboard(app: FastAPI, *, dashboard_yaml: Optional[Path] = None) -> DashboardState:
    """Wire static files, Jinja2 templates, and dashboard routes onto `app`.

    Loads `dashboard.yaml`, builds widget instances, mounts /dashboard/static,
    and registers GET routes (/, /page/{name}). Returns the state so the
    lifespan handler can later attach a RefreshOrchestrator to a scheduler.

    Raises if dashboard.yaml is missing or invalid — operators should see
    that immediately rather than ship a silently-broken page.
    """
    dashboard_yaml = dashboard_yaml or _resolve_dashboard_yaml()
    # Importing the widgets package side-effects registration of every concrete
    # widget into WIDGET_REGISTRY. We do it inside mount_dashboard rather than
    # at module import time so a single broken widget can't poison the whole
    # FastAPI app at import.
    import sigil.dashboard.widgets  # noqa: F401

    config = load_dashboard(dashboard_yaml)
    widgets = build_widget_instances(config)
    cache = WidgetCache()
    templates = Jinja2Templates(directory=str(TEMPLATES_DIR))

    state = DashboardState(config=config, widgets=widgets, cache=cache, templates=templates)
    app.state.dashboard = state

    app.mount(
        "/dashboard/static",
        StaticFiles(directory=str(STATIC_DIR)),
        name="dashboard_static",
    )

    _register_routes(app, state)
    return state


def _resolve_dashboard_yaml() -> Path:
    """Walk up from the package toward the repo root looking for dashboard.yaml."""
    candidates = [
        Path.cwd() / "dashboard.yaml",
        _PACKAGE_ROOT.parent.parent.parent / "dashboard.yaml",  # repo root from src/sigil/dashboard
        _PACKAGE_ROOT.parent.parent / "dashboard.yaml",
    ]
    for candidate in candidates:
        if candidate.exists():
            return candidate
    raise FileNotFoundError(
        "dashboard.yaml not found. Looked in: " + ", ".join(str(c) for c in candidates)
    )


def _default_page(config: DashboardConfig) -> Optional[Page]:
    for p in config.pages:
        if p.default:
            return p
    if config.pages:
        return config.pages[0]
    return None


def _widgets_for_page(state: DashboardState, page: Page) -> List[List[WidgetBase]]:
    """Group widgets by column, in YAML order. Walks `state.widgets` in order
    because `build_widget_instances` produces them page-by-page, column-by-
    column, widget-by-widget — the same iteration the loader uses internally.
    """
    by_column: List[List[WidgetBase]] = []
    cursor = _widget_cursor(state.config, state.widgets)
    for column in page.columns:
        col_widgets: List[WidgetBase] = []
        for _ in column.widgets:
            try:
                col_widgets.append(next(cursor[page.name]))
            except StopIteration:
                break
        by_column.append(col_widgets)
    return by_column


def _widget_cursor(config: DashboardConfig, widgets: List[WidgetBase]) -> Dict[str, Any]:
    """Build per-page iterators over `widgets`, in the order
    build_widget_instances produced them (page → column → widget)."""
    iterators: Dict[str, Any] = {}
    idx = 0
    for page in config.pages:
        chunk: List[WidgetBase] = []
        for column in page.columns:
            for _ in column.widgets:
                chunk.append(widgets[idx])
                idx += 1
        iterators[page.name] = iter(chunk)
    return iterators


def _render_widget(widget: WidgetBase, cache: WidgetCache) -> Markup:
    """Render a widget from its cached data; on miss, return a loading
    placeholder. Never blocks the request waiting on a fetch."""
    if widget.last_error is not None:
        return widget.render_error(widget.last_error)

    entry = cache.get((widget.type, widget.cache_key()))
    if entry is None:
        return Markup(
            f'<div class="widget" data-widget-type="{widget.type}">'
            '<div class="widget-loading">Loading...</div>'
            "</div>"
        )
    try:
        return widget.render(entry.value)
    except Exception as exc:  # pragma: no cover - defensive
        logger.warning("widget render failed: type=%s err=%s", widget.type, exc)
        return widget.render_error(exc)


def _nav_pages(config: DashboardConfig) -> List[Dict[str, str]]:
    return [{"name": p.name, "title": p.title} for p in config.pages]


def _render_page(state: DashboardState, request: Request, page: Page) -> HTMLResponse:
    columns_data = _widgets_for_page(state, page)
    rendered_columns = []
    for col_widgets in columns_data:
        rendered_columns.append(
            {
                "widgets_html": [_render_widget(w, state.cache) for w in col_widgets],
            }
        )
    column_spans = [c.size for c in page.columns]

    context = {
        "request": request,
        "page": {"name": page.name, "title": page.title},
        "page_title": page.title,
        "current_page": page.name,
        "nav_pages": _nav_pages(state.config),
        "columns": rendered_columns,
        "column_spans": column_spans,
        "theme": state.config.theme.model_dump(),
        "now_iso": datetime.now(timezone.utc).isoformat(),
    }
    return state.templates.TemplateResponse(request, "page.html", context)


def _register_routes(app: FastAPI, state: DashboardState) -> None:
    @app.get("/", include_in_schema=False)
    async def _root() -> RedirectResponse:
        page = _default_page(state.config)
        if page is None:
            return RedirectResponse(url="/page/_missing", status_code=302)
        return RedirectResponse(url=f"/page/{page.name}", status_code=302)

    @app.get("/page/{page_name}", include_in_schema=False)
    async def _page(page_name: str, request: Request) -> HTMLResponse:
        page = next((p for p in state.config.pages if p.name == page_name), None)
        if page is None:
            ctx = {
                "request": request,
                "page_title": "Not found",
                "current_page": None,
                "nav_pages": _nav_pages(state.config),
                "theme": state.config.theme.model_dump(),
                "now_iso": datetime.now(timezone.utc).isoformat(),
                "requested_name": page_name,
            }
            return state.templates.TemplateResponse(request, "404.html", ctx, status_code=404)
        try:
            return _render_page(state, request, page)
        except Exception as exc:  # pragma: no cover - defensive
            logger.exception("dashboard page render failed: %s", exc)
            ctx = {
                "request": request,
                "page_title": "Error",
                "current_page": None,
                "nav_pages": _nav_pages(state.config),
                "theme": state.config.theme.model_dump(),
                "now_iso": datetime.now(timezone.utc).isoformat(),
            }
            return state.templates.TemplateResponse(request, "error.html", ctx, status_code=500)


def start_orchestrator(state: DashboardState, scheduler: Any, session_factory: Any) -> None:
    """Hook called from the lifespan handler once the scheduler is running."""
    orch = RefreshOrchestrator(state.widgets, state.cache)
    orch.start(scheduler, session_factory)
    state.orchestrator = orch
