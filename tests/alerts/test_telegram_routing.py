"""W2.3.4 — Telegram severity → channel routing.

Each severity (critical/warning/info) routes to its own chat_id. Missing
per-severity overrides fall back to the default chat. No-op when the routed
chat is fully unconfigured. We use respx to intercept the httpx POST and
assert the payload's `chat_id`.
"""
from __future__ import annotations

import httpx
import pytest
import respx

from sigil.alerts.telegram import SEVERITIES, TelegramAlerts


pytestmark = pytest.mark.critical


def _alerts() -> TelegramAlerts:
    return TelegramAlerts(
        bot_token="TEST_TOKEN",
        chat_id="CHAT_DEFAULT",
        chat_critical="CHAT_CRITICAL",
        chat_warning="CHAT_WARNING",
        chat_info="CHAT_INFO",
    )


def test_severity_set_is_locked():
    assert SEVERITIES == ("critical", "warning", "info")


def test_chat_for_severity_uses_per_severity_chat():
    a = _alerts()
    assert a.chat_for_severity("critical") == "CHAT_CRITICAL"
    assert a.chat_for_severity("warning") == "CHAT_WARNING"
    assert a.chat_for_severity("info") == "CHAT_INFO"


def test_chat_for_severity_falls_back_to_default():
    a = TelegramAlerts(bot_token="t", chat_id="DEFAULT_ONLY")
    assert a.chat_for_severity("critical") == "DEFAULT_ONLY"
    assert a.chat_for_severity("warning") == "DEFAULT_ONLY"
    assert a.chat_for_severity("info") == "DEFAULT_ONLY"


def test_chat_for_unknown_severity_raises():
    a = _alerts()
    with pytest.raises(ValueError):
        a.chat_for_severity("debug")


@pytest.mark.asyncio
@respx.mock
async def test_send_alert_routes_critical_to_critical_chat():
    a = _alerts()
    route = respx.post("https://api.telegram.org/botTEST_TOKEN/sendMessage").mock(
        return_value=httpx.Response(200, json={"ok": True})
    )
    used = await a.send_alert("DB down", severity="critical")
    assert used == "CHAT_CRITICAL"
    assert route.called
    sent = route.calls.last.request
    import json as _json
    assert _json.loads(sent.content)["chat_id"] == "CHAT_CRITICAL"


@pytest.mark.asyncio
@respx.mock
async def test_send_alert_routes_warning_to_warning_chat():
    a = _alerts()
    route = respx.post("https://api.telegram.org/botTEST_TOKEN/sendMessage").mock(
        return_value=httpx.Response(200, json={"ok": True})
    )
    await a.send_alert("Latency spike", severity="warning")
    import json as _json
    assert _json.loads(route.calls.last.request.content)["chat_id"] == "CHAT_WARNING"


@pytest.mark.asyncio
@respx.mock
async def test_send_alert_routes_info_to_info_chat():
    a = _alerts()
    route = respx.post("https://api.telegram.org/botTEST_TOKEN/sendMessage").mock(
        return_value=httpx.Response(200, json={"ok": True})
    )
    await a.send_alert("Sync complete", severity="info")
    import json as _json
    assert _json.loads(route.calls.last.request.content)["chat_id"] == "CHAT_INFO"


@pytest.mark.asyncio
@respx.mock
async def test_send_alert_falls_back_to_default_when_severity_chat_unset():
    a = TelegramAlerts(bot_token="TEST_TOKEN", chat_id="CHAT_DEFAULT")
    route = respx.post("https://api.telegram.org/botTEST_TOKEN/sendMessage").mock(
        return_value=httpx.Response(200, json={"ok": True})
    )
    used = await a.send_alert("hello", severity="critical")
    assert used == "CHAT_DEFAULT"
    import json as _json
    assert _json.loads(route.calls.last.request.content)["chat_id"] == "CHAT_DEFAULT"


@pytest.mark.asyncio
async def test_send_alert_noop_when_no_chat_configured():
    a = TelegramAlerts(bot_token="t", chat_id=None)
    used = await a.send_alert("hello", severity="critical")
    assert used is None


@pytest.mark.asyncio
@respx.mock
async def test_send_alert_noop_when_token_missing():
    a = TelegramAlerts(bot_token=None, chat_id="CHAT", chat_critical="CRIT")
    # No HTTP route → if anything is posted, respx will raise
    used = await a.send_alert("hello", severity="critical")
    assert used == "CRIT"  # routing decision still returned


@pytest.mark.asyncio
@respx.mock
async def test_send_signal_routes_via_info():
    a = _alerts()
    route = respx.post("https://api.telegram.org/botTEST_TOKEN/sendMessage").mock(
        return_value=httpx.Response(200, json={"ok": True})
    )
    await a.send_signal(
        market_title="NBA Finals Game 7",
        model_id="elo_v2",
        edge=0.12,
        confidence=0.88,
        platform="kalshi",
    )
    import json as _json
    assert _json.loads(route.calls.last.request.content)["chat_id"] == "CHAT_INFO"
