from typing import List, Literal, Tuple
from dataclasses import dataclass
from sigil.ingestion.base import DataSource
from sigil.features.base import FeatureExtractor
from sigil.modeling.base import Model

@dataclass
class VerticalModule:
    name: str
    taxonomy_prefix: Tuple[str, str]

    # Data layer
    data_sources: List[DataSource]
    feature_extractors: List[FeatureExtractor]

    # Model layer
    models: List[Model]

    # Execution rules
    min_edge_threshold: float
    max_position_pct: float
    kelly_fraction: float
    execution_mode: Literal["passive", "aggressive", "scaled"]
