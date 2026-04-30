from __future__ import annotations

from sigil.api.server import _bind_banner, app
from sigil.config import config


def test_default_bind_is_localhost_not_zero():
    assert config.API_BIND_HOST == "127.0.0.1"
    assert config.API_BIND_HOST != "0.0.0.0"


def test_bind_banner_marks_public_exposure():
    msg = _bind_banner("0.0.0.0", 8000)
    assert "PUBLIC EXPOSURE" in msg


def test_bind_banner_marks_local():
    msg = _bind_banner("127.0.0.1", 8000)
    assert "local/tailscale" in msg


def test_bind_banner_tailscale_address_treated_as_local():
    msg = _bind_banner("100.64.1.5", 8000)
    assert "local/tailscale" in msg
    assert "PUBLIC EXPOSURE" not in msg


def test_cors_middleware_uses_frontend_origin():
    # Locate the CORS middleware in the user_middleware stack and verify origins.
    cors = None
    for mw in app.user_middleware:
        if mw.cls.__name__ == "CORSMiddleware":
            cors = mw
            break
    assert cors is not None, "CORSMiddleware not installed"
    origins = cors.kwargs.get("allow_origins") or []
    assert config.FRONTEND_ORIGIN in origins
