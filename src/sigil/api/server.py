import logging
from contextlib import asynccontextmanager
from typing import Optional

import uvicorn
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from sigil.api.routes import router
from sigil.config import config
from sigil.db import AsyncSessionLocal, init_db
from sigil.secrets import inject_into_config, load_secrets

logger = logging.getLogger(__name__)


_scheduler: Optional[AsyncIOScheduler] = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    global _scheduler
    await init_db()
    secrets = load_secrets()
    if secrets:
        inject_into_config(secrets)
        logger.info(f"Loaded {len(secrets)} secret(s) from sops.")

    if config.DASHBOARD_ENABLED:
        # Local imports keep the dashboard's pydantic models off the import
        # path of any test that doesn't opt in.
        from sigil.dashboard.mount import start_orchestrator

        state = getattr(app.state, "dashboard", None)
        if state is None:
            logger.warning("DASHBOARD_ENABLED=true but app.state.dashboard is None")
        else:
            scheduler = AsyncIOScheduler()
            scheduler.start()
            _scheduler = scheduler
            start_orchestrator(state, scheduler, lambda: AsyncSessionLocal())
            logger.info(
                "Dashboard refresh orchestrator started (%d widgets)",
                len(state.widgets),
            )

    try:
        yield
    finally:
        if _scheduler is not None:
            _scheduler.shutdown(wait=False)
            _scheduler = None


app = FastAPI(title="Sigil Dashboard API", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[config.FRONTEND_ORIGIN],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(router)


# Mount the Jinja2 dashboard surface eagerly so its routes are registered for
# any TestClient that flips DASHBOARD_ENABLED at runtime. Mounting is
# best-effort: if dashboard.yaml is absent (e.g. in a stripped CI image),
# log and continue — the JSON API still serves.
def _try_mount_dashboard() -> None:
    try:
        from sigil.dashboard.mount import mount_dashboard

        mount_dashboard(app)
    except Exception as exc:
        logger.warning("Dashboard mount skipped: %s", exc)


_try_mount_dashboard()


def _bind_banner(host: str, port: int) -> str:
    exposure = "PUBLIC EXPOSURE — VERIFY" if host == "0.0.0.0" else "local/tailscale only"
    return f"Sigil API listening on {host}:{port} ({exposure})"


def _dashboard_banner(host: str, port: int) -> str:
    return f"Dashboard at http://{host}:{port}/"


if __name__ == "__main__":
    host = config.API_BIND_HOST
    port = config.API_BIND_PORT
    print(_bind_banner(host, port))
    print(_dashboard_banner(host, port))
    uvicorn.run("sigil.api.server:app", host=host, port=port, reload=True)
