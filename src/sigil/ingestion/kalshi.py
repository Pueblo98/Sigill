import httpx
import pandas as pd
from typing import Any, List
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
