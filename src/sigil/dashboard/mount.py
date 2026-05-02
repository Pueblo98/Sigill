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
    """Topbar nav entries — YAML-defined pages plus the standalone routes
    (``/markets``, ``/execution``, ``/models``). Each entry exposes a
    ``url`` so the topbar can point to either ``/page/{name}`` or a
    hand-wired route.

    Pages dropped from topbar walking (per sigil-frontend/DESIGN.md
    "vertical IA" rule — sub-navigation lives inside the section, not
    as new top-level entries):

    - ``markets`` / ``models`` — superseded by the standalone routes.
    - ``spreads`` — moved into the Markets page as the
      ``/markets?view=spreads`` tab. The YAML page is kept so the
      ``cross_platform_spreads`` widget continues to instantiate +
      refresh; ``/page/spreads`` still renders directly for old
      bookmarks but is no longer surfaced in the topbar.
    """
    entries: List[Dict[str, str]] = []
    seen_names: set[str] = set()
    for p in config.pages:
        if p.name in ("markets", "models", "spreads"):
            continue
        entries.append({"name": p.name, "title": p.title, "url": f"/page/{p.name}"})
        seen_names.add(p.name)
    # Standalone Markets explorer — search + filter + paginate, plus
    # in-page sub-tabs for cross-platform spreads + archived markets.
    entries.insert(
        min(1, len(entries)),
        {"name": "markets", "title": "Markets", "url": "/markets"},
    )
    # Execution log — filtered + paginated orders feed. Sits next to
    # Markets so the operator's natural reading order is markets →
    # execution → models → health.
    entries.insert(
        min(2, len(entries)),
        {"name": "execution", "title": "Execution", "url": "/execution"},
    )
    # Models card grid — one card per registered model, click-through to
    # /models/{id} for the per-model deep dive.
    entries.insert(
        min(3, len(entries)),
        {"name": "models", "title": "Models", "url": "/models"},
    )
    return entries


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

    @app.get("/markets", include_in_schema=False)
    async def _markets_list(
        request: Request,
        view: Optional[str] = None,
        q: Optional[str] = None,
        platform: Optional[str] = None,
        category: Optional[str] = None,
        status: Optional[str] = None,
        archived: Optional[str] = None,
        page: Optional[str] = None,
    ) -> HTMLResponse:
        # Local imports keep dashboard pydantic models off the critical
        # path of any test that doesn't opt in.
        from sigil.dashboard.views.markets_list import (
            ALL_VIEWS,
            build_context as _build_markets_context,
        )
        from sigil.db import AsyncSessionLocal

        # Legacy ?archived=1 → ?view=archived translation. Keeps old
        # bookmarks working after the 2026-05-02 sub-tabs slice.
        if view is None and archived and archived.lower() in ("1", "true", "yes", "on"):
            view = "archived"
        # Normalise unknown / empty view to "all" so downstream code
        # only ever sees the three legal values.
        view_normalised = (view or "all").strip().lower()
        if view_normalised not in ALL_VIEWS:
            view_normalised = "all"

        # Spreads tab — render the cross_platform_spreads widget HTML
        # inline. The widget is instantiated by the YAML 'spreads' page
        # and refreshed by the orchestrator on its 5m TTL; we just pull
        # the cached value here.
        spreads_widget_html = None
        if view_normalised == "spreads":
            spreads_widget = next(
                (w for w in state.widgets if w.type == "cross_platform_spreads"),
                None,
            )
            if spreads_widget is not None:
                spreads_widget_html = _render_widget(spreads_widget, state.cache)
            else:
                spreads_widget_html = Markup(
                    '<div class="markets-list__embedded-empty">'
                    "Cross-platform spreads widget is not configured."
                    "</div>"
                )

        # The table-driven views (all + archived) need the SQL-backed
        # context. Skip the build for the spreads tab — it doesn't
        # render the markets table at all.
        if view_normalised == "spreads":
            ctx = None
        else:
            async with AsyncSessionLocal() as session:
                ctx = await _build_markets_context(
                    session,
                    view=view_normalised,
                    q=q,
                    platform=platform,
                    category=category,
                    status=status,
                    page=page,
                )

        page_ctx = {
            "request": request,
            "page_title": "Markets",
            "current_page": "markets",
            "nav_pages": _nav_pages(state.config),
            "theme": state.config.theme.model_dump(),
            "now_iso": datetime.now(timezone.utc).isoformat(),
            "view": view_normalised,
            "spreads_widget_html": spreads_widget_html,
            # Defaults for the spreads tab so the template can guard on
            # ``view == 'spreads'`` without referencing missing keys.
            "rows": ctx.rows if ctx else [],
            "total": ctx.total if ctx else 0,
            "page": ctx.page if ctx else 1,
            "page_size": ctx.page_size if ctx else 50,
            "total_pages": ctx.total_pages if ctx else 1,
            "q": ctx.q if ctx else "",
            "platform": ctx.platform if ctx else "",
            "category": ctx.category if ctx else "",
            "status": ctx.status if ctx else "",
            "platforms": ctx.platforms if ctx else [],
            "categories": ctx.categories if ctx else [],
            "statuses": ctx.statuses if ctx else [],
        }
        return state.templates.TemplateResponse(
            request, "markets_list.html", page_ctx
        )

    @app.get("/execution", include_in_schema=False)
    async def _execution_log(
        request: Request,
        platform: Optional[str] = None,
        mode: Optional[str] = None,
        status: Optional[str] = None,
        page: Optional[str] = None,
    ) -> HTMLResponse:
        # Local imports keep dashboard pydantic models off the critical
        # path of any test that doesn't opt in.
        from sigil.dashboard.views.execution_log import build_context as _build_exec_context
        from sigil.db import AsyncSessionLocal

        async with AsyncSessionLocal() as session:
            ctx = await _build_exec_context(
                session,
                platform=platform,
                mode=mode,
                status=status,
                page=page,
            )
        page_ctx = {
            "request": request,
            "page_title": "Execution",
            "current_page": "execution",
            "nav_pages": _nav_pages(state.config),
            "theme": state.config.theme.model_dump(),
            "now_iso": datetime.now(timezone.utc).isoformat(),
            "rows": ctx.rows,
            "total": ctx.total,
            "page": ctx.page,
            "page_size": ctx.page_size,
            "total_pages": ctx.total_pages,
            "platform": ctx.platform,
            "mode": ctx.mode,
            "status": ctx.status,
            "platforms": ctx.platforms,
            "modes": ctx.modes,
            "statuses": ctx.statuses,
        }
        return state.templates.TemplateResponse(
            request, "execution_log.html", page_ctx
        )

    @app.get("/models", include_in_schema=False)
    async def _models_list(request: Request) -> HTMLResponse:
        # Local imports keep dashboard pydantic models off the critical
        # path of any test that doesn't opt in.
        from sigil.dashboard.views.models_list import build_context as _build_models_context
        from sigil.db import AsyncSessionLocal

        async with AsyncSessionLocal() as session:
            ctx = await _build_models_context(session)
        page_ctx = {
            "request": request,
            "page_title": "Models",
            "current_page": "models",
            "nav_pages": _nav_pages(state.config),
            "theme": state.config.theme.model_dump(),
            "now_iso": datetime.now(timezone.utc).isoformat(),
            "cards": ctx.cards,
            "total": ctx.total,
        }
        return state.templates.TemplateResponse(
            request, "models_list.html", page_ctx
        )

    @app.get("/models/{model_id}", include_in_schema=False)
    async def _model_detail(model_id: str, request: Request) -> HTMLResponse:
        # Local imports keep dashboard pydantic models off the critical
        # path of any test that doesn't opt in.
        from sigil.dashboard.views.model_detail import build_context as _build_model_context
        from sigil.db import AsyncSessionLocal

        async with AsyncSessionLocal() as session:
            ctx = await _build_model_context(session, model_id, theme=state.config.theme)
        if ctx is None:
            ctx_404 = {
                "request": request,
                "page_title": "Model not found",
                "current_page": None,
                "nav_pages": _nav_pages(state.config),
                "theme": state.config.theme.model_dump(),
                "now_iso": datetime.now(timezone.utc).isoformat(),
                "requested_name": model_id,
            }
            return state.templates.TemplateResponse(
                request, "404.html", ctx_404, status_code=404
            )
        page_ctx = {
            "request": request,
            "page_title": ctx.display_name,
            "current_page": "models",
            "nav_pages": _nav_pages(state.config),
            "theme": state.config.theme.model_dump(),
            "now_iso": datetime.now(timezone.utc).isoformat(),
            "model_id": ctx.model_id,
            "version": ctx.version,
            "display_name": ctx.display_name,
            "description": ctx.description,
            "tags": ctx.tags,
            "enabled": ctx.enabled,
            "summary": ctx.summary,
            "equity_curve_svg": ctx.equity_curve_svg,
            "equity_curve_points": ctx.equity_curve_points,
            "recent_trades": ctx.recent_trades,
            "recent_predictions": ctx.recent_predictions,
        }
        return state.templates.TemplateResponse(
            request, "model_detail.html", page_ctx
        )

    @app.get("/market/{external_id}", include_in_schema=False)
    async def _market_detail(external_id: str, request: Request) -> HTMLResponse:
        # Local imports keep the dashboard's pydantic models off the
        # critical path of any test that doesn't opt in.
        from sigil.dashboard.views.market_detail import build_context
        from sigil.db import AsyncSessionLocal

        async with AsyncSessionLocal() as session:
            ctx = await build_context(session, external_id, theme=state.config.theme)
        if ctx is None:
            ctx_404 = {
                "request": request,
                "page_title": "Market not found",
                "current_page": None,
                "nav_pages": _nav_pages(state.config),
                "theme": state.config.theme.model_dump(),
                "now_iso": datetime.now(timezone.utc).isoformat(),
                "requested_name": external_id,
            }
            return state.templates.TemplateResponse(
                request, "404.html", ctx_404, status_code=404
            )
        page_ctx = {
            "request": request,
            "page_title": ctx.market.title,
            "current_page": None,
            "nav_pages": _nav_pages(state.config),
            "theme": state.config.theme.model_dump(),
            "now_iso": datetime.now(timezone.utc).isoformat(),
            "market": ctx.market,
            "breadcrumb": ctx.breadcrumb,
            "latest_price": ctx.latest_price,
            "sparkline_svg": ctx.sparkline_svg,
            "price_history": ctx.price_history,
            "orderbook": ctx.orderbook,
            "latest_prediction": ctx.latest_prediction,
            "predictions": ctx.predictions,
            "lifecycle": ctx.lifecycle,
            "siblings_event": ctx.siblings_event,
            "siblings_taxonomy": ctx.siblings_taxonomy,
        }
        return state.templates.TemplateResponse(
            request, "market_detail.html", page_ctx
        )

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
