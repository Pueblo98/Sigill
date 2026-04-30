import logging
from contextlib import asynccontextmanager

import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from sigil.api.routes import router
from sigil.config import config
from sigil.db import init_db
from sigil.secrets import inject_into_config, load_secrets

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(_: FastAPI):
    await init_db()
    secrets = load_secrets()
    if secrets:
        inject_into_config(secrets)
        logger.info(f"Loaded {len(secrets)} secret(s) from sops.")
    yield


app = FastAPI(title="Sigil Dashboard API", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[config.FRONTEND_ORIGIN],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(router)


def _bind_banner(host: str, port: int) -> str:
    exposure = "PUBLIC EXPOSURE — VERIFY" if host == "0.0.0.0" else "local/tailscale only"
    return f"Sigil API listening on {host}:{port} ({exposure})"


if __name__ == "__main__":
    host = config.API_BIND_HOST
    port = config.API_BIND_PORT
    print(_bind_banner(host, port))
    uvicorn.run("sigil.api.server:app", host=host, port=port, reload=True)
