"""Central extraction contract registry for Review Master.

Identifies incoming extraction contracts, validates payloads against versioned schemas,
and resolves the appropriate ExtractionContractAdapter.
"""

from typing import Any

from app.contracts.extraction.adapters.generalized_v1_adapter import (
    GeneralizedExtractionAdapter,
)
from app.contracts.extraction.adapters.smartphone_v1_adapter import (
    SmartphoneExtractionV1Adapter,
)
from app.contracts.extraction.base import (
    ExtractionContractAdapter,
    UnsupportedContractError,
    UnsupportedVersionError,
)
from app.contracts.extraction.canonical import CanonicalInternalExtraction


class ExtractionContractRegistry:
    """Registry maintaining active extraction contract adapters and version resolution."""

    def __init__(self):
        self._adapters: dict[str, ExtractionContractAdapter] = {}
        # Register standard adapters
        self.register_adapter(SmartphoneExtractionV1Adapter())
        self.register_adapter(GeneralizedExtractionAdapter())

    def register_adapter(self, adapter: ExtractionContractAdapter) -> None:
        """Register an extraction adapter instance."""
        self._adapters[adapter.contract_name] = adapter

    def identify_contract(self, payload: dict[str, Any]) -> tuple[str, str]:
        """Identify (contract_name, schema_version) from raw payload without guessing.

        Raises:
            UnsupportedContractError: If payload structure does not match any recognized contract.
            UnsupportedVersionError: If schema_version is missing or unsupported.
        """
        if not isinstance(payload, dict):
            raise UnsupportedContractError("Payload must be a JSON object.")

        # 1. Check for Generalized Extraction Contract (envelope with 'contract' block)
        if "contract" in payload and isinstance(payload["contract"], dict):
            contract_meta = payload["contract"]
            c_type = contract_meta.get("contract_type")
            s_ver = contract_meta.get("schema_version")
            if c_type == "generalized_extraction":
                if not s_ver:
                    raise UnsupportedVersionError("Generalized contract is missing 'contract.schema_version'.")
                return ("generalized_extraction", str(s_ver))

        # 2. Check for Smartphone Extraction Contract
        # If payload has normalized, raw_extraction, or category smartphone hints
        has_smartphone_hints = (
            "raw_extraction" in payload
            or "normalized" in payload
            or (isinstance(payload.get("normalized"), dict) and payload["normalized"].get("category") == "smartphone")
            or (isinstance(payload.get("source"), dict) and "amazon.in" in str(payload["source"].get("marketplace", "")))
        )
        if has_smartphone_hints:
            s_ver = payload.get("schema_version")
            if not s_ver:
                raise UnsupportedVersionError("Smartphone extraction payload is missing 'schema_version'.")
            return ("smartphone_extraction", str(s_ver))

        raise UnsupportedContractError(
            "Unrecognized extraction payload structure. Must conform to either "
            "frozen smartphone extraction contract or generalized extraction contract."
        )

    def get_adapter(self, contract_name: str, schema_version: str) -> ExtractionContractAdapter:
        """Resolve adapter for given contract name and schema version.

        Raises:
            UnsupportedContractError: If contract is not registered.
            UnsupportedVersionError: If schema version is not supported by the adapter.
        """
        adapter = self._adapters.get(contract_name)
        if not adapter:
            raise UnsupportedContractError(f"No adapter registered for contract '{contract_name}'.")

        if schema_version not in adapter.supported_versions:
            raise UnsupportedVersionError(
                f"Schema version '{schema_version}' is not supported by contract '{contract_name}'. "
                f"Supported versions: {sorted(adapter.supported_versions)}."
            )

        return adapter

    def resolve_and_validate(
        self,
        payload: dict[str, Any],
    ) -> tuple[ExtractionContractAdapter, str, str]:
        """Identify contract, resolve adapter, and validate payload.

        Returns:
            tuple: (adapter, contract_name, schema_version)
        """
        contract_name, schema_version = self.identify_contract(payload)
        adapter = self.get_adapter(contract_name, schema_version)
        adapter.validate(payload)
        return (adapter, contract_name, schema_version)

    def to_canonical(
        self,
        payload: dict[str, Any],
        *,
        record_id: str | None = None,
        storage_object_key: str | None = None,
        sha256_digest: str | None = None,
    ) -> CanonicalInternalExtraction:
        """End-to-end convenience method to identify, validate, and convert payload to canonical."""
        adapter, _, _ = self.resolve_and_validate(payload)
        return adapter.to_canonical(
            payload,
            record_id=record_id,
            storage_object_key=storage_object_key,
            sha256_digest=sha256_digest,
        )


# Global singleton instance
contract_registry = ExtractionContractRegistry()
