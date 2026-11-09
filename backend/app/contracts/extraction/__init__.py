"""Extraction contracts and compatibility layer package."""

from app.contracts.extraction.canonical import (
    CanonicalExtractedAttribute,
    CanonicalInternalExtraction,
)
from app.contracts.extraction.registry import (
    ExtractionContractRegistry,
    contract_registry,
)

__all__ = [
    "CanonicalExtractedAttribute",
    "CanonicalInternalExtraction",
    "ExtractionContractRegistry",
    "contract_registry",
]

