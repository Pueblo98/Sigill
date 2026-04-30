import httpx
import pandas as pd
from typing import Any, List, AsyncIterator
import websockets
import json
from sigil.ingestion.base import DataSource
from sigil.config import config
class KalshiDataSource(DataSource):
    name: str = "kalshi_markets"
    refresh_interval: int = 60  # seconds

    def __init__(self, base_url: str = "https://trading-api.kalshi.com/trade-api/v2"):
        self.base_url = base_url
        self.client = httpx.AsyncClient(base_url=base_url)

    async def fetch(self) -> List[dict]:
        """Fetch active markets from Kalshi."""
        response = await self.client.get("/markets")
        response.raise_for_status()
        return response.json().get("markets", [])

    async def stream_prices(self, market_ids: List[str]) -> AsyncIterator[dict]:
        """Stream real-time orderbook updates from Kalshi WebSocket."""
        ws_url = "wss://trading-api.kalshi.com/trade-api/ws/v2"
        # Using a simple unauthenticated connection for public market data streaming
        async with websockets.connect(ws_url) as ws:
            subscribe_msg = {
                "id": 1,
                "cmd": "subscribe",
                "params": {
                    "channels": ["orderbook_delta"],
                    "market_tickers": market_ids
                }
            }
            await ws.send(json.dumps(subscribe_msg))
            
            async for message in ws:
                data = json.loads(message)
                if data.get("type") == "orderbook_delta":
                    msg_data = data.get("msg", {})
                    market_id = msg_data.get("market_ticker")
                    
                    bids = msg_data.get("bids", [])
                    asks = msg_data.get("asks", [])
                    
                    # Prices in Kalshi are in cents
                    best_bid = (bids[0][0] / 100.0) if bids else None
                    best_ask = (asks[0][0] / 100.0) if asks else None
                    
                    yield {
                        "market_id": market_id,
                        "platform": "kalshi",
                        "bid": best_bid,
                        "ask": best_ask,
                        "last_price": best_bid,  # approximate if last_price not in delta
                        "time": pd.Timestamp.utcnow(),
                        "volume_24h": None,
                        "open_interest": None,
                        "source": "exchange_ws"
                    }

    def normalize(self, raw_data: List[dict]) -> pd.DataFrame:
        """Normalize Kalshi market data into a standard DataFrame."""
        normalized = []
        for m in raw_data:
            normalized.append({
                "external_id": m.get("ticker"),
                "platform": "kalshi",
                "title": m.get("title"),
                "taxonomy_l1": m.get("category", "unknown").lower(),
                "market_type": "binary",
                "status": m.get("status", "open").lower(),
                "resolution_date": m.get("close_time"),
            })
        return pd.DataFrame(normalized)

    def validate(self, df: pd.DataFrame) -> bool:
        """Simple validation check on the normalized data."""
        required_cols = {"external_id", "platform", "title", "taxonomy_l1"}
        return required_cols.issubset(df.columns) and not df.empty
