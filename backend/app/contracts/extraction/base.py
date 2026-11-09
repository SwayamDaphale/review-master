"""Base protocols, abstractions, and exceptions for extraction contracts."""

from abc import ABC, abstractmethod
from typing import Any

from app.contracts.extraction.canonical import CanonicalInternalExtraction


class ContractException(Exception):
    """Base exception for all contract-related errors."""


class ContractValidationError(ContractException):
    """Raised when an incoming extraction payload violates its schema contract."""

    def __init__(self, message: str, errors: list[dict[str, Any]] | None = None):
        super().__init__(message)
        self.message = message
        self.errors = errors or []


class UnsupportedContractError(ContractException):
    """Raised when an incoming payload does not match any recognized contract."""


class UnsupportedVersionError(ContractException):
    """Raised when an extraction payload presents an unversioned or unsupported schema version."""


class ExtractionContractAdapter(ABC):
    """Abstract protocol for versioned extraction contract adapters."""

    @property
    @abstractmethod
    def contract_name(self) -> str:
        """Name identifying the contract (e.g. 'smartphone_extraction', 'generalized_extraction')."""

    @property
    @abstractmethod
    def supported_versions(self) -> set[str]:
        """Set of supported schema version strings (e.g. {'1.0', '1.0.0'})."""

    @abstractmethod
    def validate(self, payload: dict[str, Any]) -> None:
        """Validate payload against contract schema. Raises ContractValidationError on mismatch."""

    @abstractmethod
    def to_canonical(
        self,
        payload: dict[str, Any],
        *,
        record_id: str | None = None,
        storage_object_key: str | None = None,
        sha256_digest: str | None = None,
    ) -> CanonicalInternalExtraction:
        """Translate valid contract payload into the unified CanonicalInternalExtraction model."""

