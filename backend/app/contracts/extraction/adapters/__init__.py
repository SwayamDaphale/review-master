"""Extraction contract adapters package."""

from app.contracts.extraction.adapters.generalized_v1_adapter import (
    GeneralizedExtractionAdapter,
)
from app.contracts.extraction.adapters.smartphone_v1_adapter import (
    SmartphoneExtractionV1Adapter,
)

__all__ = [
    "GeneralizedExtractionAdapter",
    "SmartphoneExtractionV1Adapter",
]
