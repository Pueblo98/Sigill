import httpx
from sigil.config import config
import logging

logger = logging.getLogger(__name__)

class TelegramAlerts:
    """
    The 'Whisper' Hub: Sends real-time signals and alerts to the operator via Telegram.
    """
    def __init__(self, bot_token: str = config.TELEGRAM_BOT_TOKEN, chat_id: str = config.TELEGRAM_CHAT_ID):
        self.bot_token = bot_token
        self.chat_id = chat_id
        self.base_url = f"https://api.telegram.org/bot{bot_token}/sendMessage"

    async def send_message(self, text: str, parse_mode: str = "MarkdownV2"):
        """Sends a message to the configured Telegram chat."""
        if not self.bot_token or not self.chat_id:
            logger.warning("Telegram alerts are not configured. Skipping message.")
            return

        payload = {
            "chat_id": self.chat_id,
            "text": text,
            "parse_mode": parse_mode
        }
        
        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(self.base_url, json=payload)
                response.raise_for_status()
        except Exception as e:
            logger.error(f"Failed to send Telegram alert: {str(e)}")

    async def send_signal(self, market_title: str, model_id: str, edge: float, confidence: float, platform: str):
        """Standardized format for sending a model-generated signal."""
        # Note: MarkdownV2 requires escaping certain characters. 
        # This is a simplified version; in production, you'd use a more robust escape function.
        msg = (
            f"🔮 *NEW SIGNAL: {market_title}*\n\n"
            f"📍 *Platform:* {platform.upper()}\n"
            f"🤖 *Model:* `{model_id}`\n"
            f"📈 *Edge:* `{edge*100:.1f}%` \n"
            f"🎯 *Confidence:* `{confidence*100:.1f}%` \n\n"
            f"[View in Dashboard](https://sigil.local/signals)"
        ).replace(".", "\\.").replace("-", "\\-") # Basic escaping for MarkdownV2

        await self.send_message(msg)
