"""Telegram alert routing.

W2.3.4: severity → channel routing. Each severity (`critical`, `warning`,
`info`) can target its own chat ID; missing per-severity overrides fall back
to `TELEGRAM_CHAT_ID`. We send via raw HTTPX rather than `python-telegram-bot`
because the only API surface we need is `sendMessage`.
"""
from __future__ import annotations

import logging
from typing import Optional

import httpx

from sigil.config import config

logger = logging.getLogger(__name__)


SEVERITIES = ("critical", "warning", "info")


class TelegramAlerts:
    """Routes alerts to per-severity chats and falls back to the default chat."""

    def __init__(
        self,
        bot_token: Optional[str] = None,
        chat_id: Optional[str] = None,
        *,
        chat_critical: Optional[str] = None,
        chat_warning: Optional[str] = None,
        chat_info: Optional[str] = None,
    ):
        self.bot_token = bot_token if bot_token is not None else config.TELEGRAM_BOT_TOKEN
        self.chat_id = chat_id if chat_id is not None else config.TELEGRAM_CHAT_ID
        self._chats = {
            "critical": chat_critical if chat_critical is not None else config.TELEGRAM_CHAT_CRITICAL,
            "warning": chat_warning if chat_warning is not None else config.TELEGRAM_CHAT_WARNING,
            "info": chat_info if chat_info is not None else config.TELEGRAM_CHAT_INFO,
        }
        self.base_url = f"https://api.telegram.org/bot{self.bot_token}/sendMessage"

    def chat_for_severity(self, severity: str) -> Optional[str]:
        if severity not in SEVERITIES:
            raise ValueError(f"unknown severity {severity!r}; expected one of {SEVERITIES}")
        return self._chats.get(severity) or self.chat_id

    async def send_message(self, text: str, parse_mode: str = "MarkdownV2") -> None:
        await self._post(self.chat_id, text, parse_mode)

    async def send_alert(self, text: str, severity: str, parse_mode: str = "MarkdownV2") -> Optional[str]:
        """Send `text` to the chat configured for `severity`. Returns the
        chat_id actually used (handy in tests). No-op when the routed chat is
        unconfigured."""
        chat = self.chat_for_severity(severity)
        if chat is None:
            logger.warning("No chat configured for severity %s; dropping alert.", severity)
            return None
        await self._post(chat, text, parse_mode)
        return chat

    async def send_signal(
        self,
        market_title: str,
        model_id: str,
        edge: float,
        confidence: float,
        platform: str,
    ) -> None:
        msg = (
            f"🔮 *NEW SIGNAL: {market_title}*\n\n"
            f"📍 *Platform:* {platform.upper()}\n"
            f"🤖 *Model:* `{model_id}`\n"
            f"📈 *Edge:* `{edge*100:.1f}%` \n"
            f"🎯 *Confidence:* `{confidence*100:.1f}%` \n\n"
            f"[View in Dashboard](https://sigil.local/signals)"
        ).replace(".", "\\.").replace("-", "\\-")
        await self.send_alert(msg, severity="info")

    async def _post(self, chat_id: Optional[str], text: str, parse_mode: str) -> None:
        if not self.bot_token or not chat_id:
            logger.warning("Telegram alerts not configured (token=%s chat=%s); skipping.",
                           bool(self.bot_token), bool(chat_id))
            return

        payload = {"chat_id": chat_id, "text": text, "parse_mode": parse_mode}
        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(self.base_url, json=payload)
                response.raise_for_status()
        except Exception as e:
            logger.error("Failed to send Telegram alert: %s", e)
