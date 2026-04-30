import httpx
import pandas as pd
from typing import Any, List, AsyncIterator
import websockets
import json
from sigil.ingestion.base import DataSource
from sigil.config import config
class PolymarketDataSource(DataSource):
    """
    Ingests market data from the Polymarket Central Limit Order Book (CLOB).
    """
    name: str = "polymarket_clob"
    refresh_interval: int = 30  # Poly is more dynamic

    def __init__(self, base_url: str = "https://clob.polymarket.com"):
        self.base_url = base_url
        self.client = httpx.AsyncClient(base_url=base_url)

    async def fetch(self) -> List[dict]:
        """Fetch active markets from Polymarket."""
        # Querying active markets via the CLOB API
        response = await self.client.get("/markets", params={"active": "true", "closed": "false"})
        response.raise_for_status()
        return response.json().get("data", [])

    async def stream_prices(self, market_ids: List[str]) -> AsyncIterator[dict]:
        """Stream real-time orderbook updates from Polymarket WebSocket."""
        ws_url = "wss://ws-subscriptions-clob.polymarket.com/ws/market"
        async with websockets.connect(ws_url) as ws:
            subscribe_msg = {
                "assets_ids": market_ids,
                "type": "market"
            }
            await ws.send(json.dumps(subscribe_msg))
            
            async for message in ws:
                data = json.loads(message)
                if isinstance(data, list):
                    for tick in data:
                        asset_id = tick.get("asset_id")
                        if not asset_id:
                            continue
                            
                        # Prices depend on Polymarket tick shape
                        price = float(tick.get("price", 0)) if "price" in tick else None
                        
                        yield {
                            "market_id": asset_id,
                            "platform": "polymarket",
                            "bid": price,
                            "ask": price,
                            "last_price": price,
                            "time": pd.Timestamp.utcnow(),
                            "volume_24h": None,
                            "open_interest": None,
                            "source": "exchange_ws"
                        }

    def normalize(self, raw_data: List[dict]) -> pd.DataFrame:
        """Standardizes Polymarket data to match Sigil taxonomy."""
        normalized = []
        for m in raw_data:
            # Polymarket events can have multiple tokens (Yes/No)
            # We map them to our internal market structure
            if not m.get("active") or m.get("closed"):
                continue # Strictly drop dead instances
                
            normalized.append({
                "external_id": m.get("condition_id"),
                "platform": "polymarket",
                "title": m.get("question", "Unknown Question"),
                "taxonomy_l1": m.get("category", "unknown").lower(),
                "market_type": "binary", # CLOB primarily binary
                "status": "open",
                "resolution_date": m.get("end_date_iso"),
            })
        return pd.DataFrame(normalized)

    def validate(self, df: pd.DataFrame) -> bool:
        return "external_id" in df.columns and not df.empty
