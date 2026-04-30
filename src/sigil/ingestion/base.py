from typing import Protocol, runtime_checkable, Any, AsyncIterator
from datetime import datetime
import pandas as pd

@runtime_checkable
class DataSource(Protocol):
    name: str
    refresh_interval: int  # in seconds

    async def fetch(self) -> Any:
        """Fetch raw data from source."""
        ...

    async def stream_prices(self, market_ids: list[str]) -> AsyncIterator[dict]:
        """Stream real-time price updates for given markets."""
        yield {}
        ...

    def normalize(self, raw_data: Any) -> pd.DataFrame:
        """Normalize raw data into a standard DataFrame."""
        ...

    def validate(self, df: pd.DataFrame) -> bool:
        """Validate normalized data schema and quality."""
        ...
