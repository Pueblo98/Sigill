from typing import Protocol, runtime_checkable, List
from datetime import timedelta
import pandas as pd

@runtime_checkable
class FeatureExtractor(Protocol):
    name: str
    version: str
    refresh_interval: timedelta
    dependencies: List[str]

    def compute(self, raw_data: pd.DataFrame) -> pd.Series:
        """Compute feature values from raw data."""
        ...
