"""End-to-end render tests for the Jinja2 dashboard surface (Lane F3).

The mounted app loads `dashboard.yaml` at import time. The TestClient drives
GET / + GET /page/{name} + the static asset routes.
"""

from __future__ import annotations

from typing import Iterator

import pytest
from fastapi.testclient import TestClient

import sigil.dashboard.widgets  # noqa: F401  registers widgets


@pytest.fixture(scope="module")
def client() -> Iterator[TestClient]:
    from sigil.api.server import app

    # We do NOT enter the lifespan (TestClient context manager) because that
    # starts APScheduler. Instead, instantiate the client without the
    # `with` form; FastAPI's TestClient still serves routes correctly.
    yield TestClient(app)


def test_root_redirects_to_default_page(client: TestClient) -> None:
    resp = client.get("/", follow_redirects=False)
    assert resp.status_code == 302
    assert resp.headers["location"] == "/page/command-center"


def test_command_center_renders_with_widget_attributes(client: TestClient) -> None:
    resp = client.get("/page/command-center")
    assert resp.status_code == 200
    body = resp.text
    # Widgets we know are configured on command-center per dashboard.yaml +
    # guaranteed to be registered (F1).
    assert 'data-widget-type="bankroll_summary"' in body
    assert 'data-widget-type="signal_queue"' in body
    assert 'data-widget-type="system_health_strip"' in body
    assert 'data-widget-type="recent_activity"' in body
    # Cache miss on first paint -> loading state wrapper appears, not 500.
    assert "Loading" in body or 'class="widget-empty"' in body or 'class="widget"' in body


def test_markets_page_includes_market_list(client: TestClient) -> None:
    resp = client.get("/page/markets")
    assert resp.status_code == 200
    assert 'data-widget-type="market_list"' in resp.text


def test_models_page_includes_open_positions(client: TestClient) -> None:
    """The 'models' page is a stub until F2 lands; it embeds open_positions
    so it isn't empty. Adjust when F2 widgets join the YAML."""
    resp = client.get("/page/models")
    assert resp.status_code == 200
    assert 'data-widget-type="open_positions"' in resp.text


def test_health_page_includes_system_health_strip(client: TestClient) -> None:
    resp = client.get("/page/health")
    assert resp.status_code == 200
    assert 'data-widget-type="system_health_strip"' in resp.text


def test_unknown_page_returns_404(client: TestClient) -> None:
    resp = client.get("/page/does-not-exist")
    assert resp.status_code == 404
    assert "not configured" in resp.text or "Page not found" in resp.text


def test_theme_variables_inlined_in_head(client: TestClient) -> None:
    resp = client.get("/page/command-center")
    assert resp.status_code == 200
    body = resp.text
    # The exact hex strings come from dashboard.yaml's `theme:` block.
    assert "#1b1b1d" in body  # background
    assert "#201f21" in body  # surface
    assert "#d2bbff" in body  # accent
    assert "--bg:" in body  # CSS variable name in inlined <style>
    assert "--accent:" in body


def test_static_css_served(client: TestClient) -> None:
    resp = client.get("/dashboard/static/dashboard.css")
    assert resp.status_code == 200
    assert "text/css" in resp.headers["content-type"]
    assert ".widget" in resp.text


def test_static_relative_time_js_served(client: TestClient) -> None:
    resp = client.get("/dashboard/static/relative-time.js")
    assert resp.status_code == 200
    ctype = resp.headers["content-type"]
    assert "javascript" in ctype or "text/" in ctype
    assert "data-relative-time" in resp.text


def test_nav_lists_all_pages(client: TestClient) -> None:
    resp = client.get("/page/command-center")
    assert resp.status_code == 200
    body = resp.text
    for href in (
        "/page/command-center",
        "/page/markets",
        "/page/models",
        "/page/health",
    ):
        assert href in body
