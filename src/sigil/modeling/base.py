from typing import Protocol, runtime_checkable, Any, Dict
from pydantic import BaseModel
import pandas as pd

class Prediction(BaseModel):
    probability: float
    confidence: float
    metadata: Dict[str, Any] = {}

@runtime_checkable
class Model(Protocol):
    model_id: str
    version: str

    def predict(self, features: pd.DataFrame) -> Prediction:
        """Generate a prediction from input features."""
        ...

    def evaluate(self, actuals: pd.Series) -> Dict[str, float]:
        """Evaluate model performance (Brier, LogLoss, etc.)."""
        ...
