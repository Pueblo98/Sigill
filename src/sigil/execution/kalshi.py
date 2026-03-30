import base64
import time
import httpx
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import padding
from cryptography.hazmat.primitives import serialization
from sigil.execution.base import ExchangeAdapter, Balance
from sigil.config import config
import logging

logger = logging.getLogger(__name__)

class KalshiAdapter(ExchangeAdapter):
    """
    Kalshi v2 API Adapter with RSA Request Signing.
    Required for executing 'Spells' (Trades) on the exchange.
    """
    def __init__(self, api_key: str, private_key_path: str, base_url: str = "https://trading-api.kalshi.com/trade-api/v2"):
        self.api_key = api_key
        self.private_key = self._load_private_key(private_key_path)
        self.base_url = base_url
        self.client = httpx.AsyncClient(base_url=base_url)

    def _load_private_key(self, path: str):
        with open(path, "rb") as key_file:
            return serialization.load_pem_private_key(
                key_file.read(),
                password=None,
            )

    def _sign_request(self, timestamp: str, method: str, path: str) -> str:
        """Creates the RSA signature required for Kalshi v2 headers."""
        msg = f"{timestamp}{method}{path}"
        signature = self.private_key.sign(
            msg.encode("utf-8"),
            padding.PSS(
                mgf=padding.MGF1(hashes.SHA256()),
                salt_length=padding.PSS.MAX_LENGTH
            ),
            hashes.SHA256()
        )
        return base64.b64encode(signature).decode("utf-8")

    def _get_headers(self, method: str, path: str) -> dict:
        timestamp = str(int(time.time() * 1000))
        signature = self._sign_request(timestamp, method, path)
        return {
            "KALSHI-ACCESS-KEY": self.api_key,
            "KALSHI-ACCESS-SIGNATURE": signature,
            "KALSHI-ACCESS-TIMESTAMP": timestamp,
            "Content-Type": "application/json"
        }

    async def get_balance(self) -> Balance:
        path = "/portfolio/balance"
        headers = self._get_headers("GET", path)
        response = await self.client.get(path, headers=headers)
        response.raise_for_status()
        data = response.json()
        return Balance(
            available=data["balance"] / 100.0, # Kalshi uses cents
            total=data["balance"] / 100.0
        )

    async def place_order(
        self, 
        market_external_id: str, 
        side: str, 
        outcome: str, 
        price: float, 
        quantity: int,
        order_type: str = "limit"
    ) -> str:
        path = "/portfolio/orders"
        # Kalshi expects prices in cents
        payload = {
            "ticker": market_external_id,
            "action": "buy" if side == "buy" else "sell",
            "type": order_type,
            "yes_price": int(price * 100) if outcome == "yes" else 100 - int(price * 100),
            "count": quantity,
            "side": outcome
        }
        headers = self._get_headers("POST", path)
        response = await self.client.post(path, json=payload, headers=headers)
        response.raise_for_status()
        return response.json()["order_id"]

    async def cancel_order(self, external_order_id: str) -> bool:
        path = f"/portfolio/orders/{external_order_id}"
        headers = self._get_headers("DELETE", path)
        response = await self.client.delete(path, headers=headers)
        return response.status_code == 200

    async def get_order_status(self, external_order_id: str) -> str:
        path = f"/portfolio/orders/{external_order_id}"
        headers = self._get_headers("GET", path)
        response = await self.client.get(path, headers=headers)
        response.raise_for_status()
        return response.json()["order"]["status"]

    async def sync_positions(self) -> List[dict]:
        path = "/portfolio/positions"
        headers = self._get_headers("GET", path)
        response = await self.client.get(path, headers=headers)
        response.raise_for_status()
        return response.json().get("positions", [])
