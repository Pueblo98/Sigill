import httpx
import pandas as pd
from typing import Any, List, Dict, Optional
from sigil.ingestion.base import DataSource
import logging

logger = logging.getLogger(__name__)

class FREDDataSource(DataSource):
    """
    Ingests economic time-series data from the St. Louis Fed (FRED).
    Key Series: CPIAUCSL (CPI), GDP, UNRATE (Unemployment).
    Used for Kalshi Macro verticals.
    """
    name: str = "fred_economic_data"
    refresh_interval: int = 86400  # Once per day (economic data doesn't change fast)

    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or os.getenv("FRED_API_KEY")
        self.base_url = "https://api.stlouisfed.org/fred/series/observations"
        self.client = httpx.AsyncClient()

    async def fetch_series(self, series_id: str) -> List[dict]:
        """Fetch observations for a specific economic series."""
        if not self.api_key:
            logger.warning("FRED API key missing. Skipping fetch.")
            return []

        params = {
            "series_id": series_id,
            "api_key": self.api_key,
            "file_type": "json",
            "sort_order": "desc",
            "limit": 10  # Get latest 10 data points
        }
        
        try:
            response = await self.client.get(self.base_url, params=params)
            response.raise_for_status()
            return response.json().get("observations", [])
        except Exception as e:
            logger.error(f"Failed to fetch FRED data for {series_id}: {e}")
            return []

    async def fetch(self) -> Dict[str, Any]:
        # Fetching a core set of macro indicators
        series_to_fetch = ["CPIAUCSL", "GDP", "UNRATE", "FEDFUNDS"]
        results = {}
        for sid in series_to_fetch:
            results[sid] = await self.fetch_series(sid)
        return results

    def normalize(self, raw_data: Dict[str, List[dict]]) -> pd.DataFrame:
        """
        Standardizes economic observations into a historical trend table.
        """
        normalized = []
        for series_id, observations in raw_data.items():
            for obs in observations:
                normalized.append({
                    "series_id": series_id,
                    "date": obs.get("date"),
                    "value": float(obs.get("value")) if obs.get("value") != "." else None
                })
        return pd.DataFrame(normalized)

    def validate(self, df: pd.DataFrame) -> bool:
        return not df.empty and "series_id" in df.columns
