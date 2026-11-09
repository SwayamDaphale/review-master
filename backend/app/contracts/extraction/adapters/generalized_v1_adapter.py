"""Adapter translating Generalized Extraction V1 payloads to CanonicalInternalExtraction."""

import uuid
from decimal import Decimal
from typing import Any

from pydantic import ValidationError

from app.contracts.extraction.base import (
    ContractValidationError,
    ExtractionContractAdapter,
)
from app.contracts.extraction.canonical import (
    CanonicalExtractedAttribute,
    CanonicalInternalExtraction,
)
from app.contracts.extraction.generalized_v1 import (
    GeneralizedExtractionV1Payload,
)


class GeneralizedExtractionAdapter(ExtractionContractAdapter):
    """Adapter for the Generalized Extraction V1 category-independent contract."""

    @property
    def contract_name(self) -> str:
        return "generalized_extraction"

    @property
    def supported_versions(self) -> set[str]:
        return {"1.0", "1.0.0"}

    def validate(self, payload: dict[str, Any]) -> None:
        """Validate payload against GeneralizedExtractionV1Payload schema."""
        contract_meta = payload.get("contract") or {}
        schema_ver = contract_meta.get("schema_version")
        if schema_ver not in self.supported_versions:
            raise ContractValidationError(
                f"Unsupported generalized contract schema version '{schema_ver}'. Expected '1.0' or '1.0.0'.",
                errors=[{"loc": ["contract", "schema_version"], "code": "unsupported_version", "msg": f"Expected 1.0 or 1.0.0, got '{schema_ver}'"}],
            )

        try:
            GeneralizedExtractionV1Payload.model_validate(payload)
        except ValidationError as e:
            errs = [
                {
                    "loc": list(err["loc"]),
                    "code": err["type"],
                    "msg": err["msg"],
                }
                for err in e.errors()
            ]
            raise ContractValidationError(
                f"Validation error in generalized extraction payload: {e}",
                errors=errs,
            ) from e

    def to_canonical(
        self,
        payload: dict[str, Any],
        *,
        record_id: str | None = None,
        storage_object_key: str | None = None,
        sha256_digest: str | None = None,
    ) -> CanonicalInternalExtraction:
        """Convert validated generalized payload into CanonicalInternalExtraction."""
        self.validate(payload)
        parsed = GeneralizedExtractionV1Payload.model_validate(payload)

        # Convert attributes
        attributes: list[CanonicalExtractedAttribute] = [
            CanonicalExtractedAttribute(
                attribute_key=attr.attribute_key,
                value_type=attr.value_type,
                value=attr.value,
                original_value=attr.original_value,
                original_unit=attr.original_unit,
                normalized_value=attr.normalized_value,
                normalized_unit=attr.normalized_unit,
                confidence=Decimal(str(attr.confidence)),
                source_reference=attr.source_reference,
            )
            for attr in parsed.extracted_data.attributes
        ]

        raw_specs = [
            {"label": item.label, "value": item.value}
            for item in parsed.raw_evidence.specifications
        ]

        resolved_rec_id = record_id or parsed.contract.record_id or str(uuid.uuid4())
        ext_data = parsed.extracted_data

        return CanonicalInternalExtraction(
            ingestion_record_id=resolved_rec_id,
            source_contract=self.contract_name,
            source_schema_version=parsed.contract.schema_version,
            marketplace=parsed.source.marketplace,
            page_type=parsed.source.page_type,
            product_category=parsed.product_context.category,
            product_url=parsed.source.product_url,
            extraction_method=parsed.source.extraction_method,
            extension_version=parsed.source.extension_version,
            extracted_at=parsed.contract.captured_at,
            asin=parsed.product_context.external_id,
            page_title=parsed.source.page_title,
            raw_title=parsed.raw_evidence.title,
            raw_brand=parsed.product_context.brand_hint,
            raw_model=parsed.product_context.model_hint,
            raw_variant=parsed.product_context.variant_hint,
            raw_price_text=parsed.raw_evidence.raw_price_text,
            raw_rating_text=parsed.raw_evidence.raw_rating_text,
            raw_review_count_text=parsed.raw_evidence.raw_review_count_text,
            raw_availability_text=parsed.raw_evidence.raw_availability_text,
            raw_specifications=raw_specs,
            price_amount=Decimal(str(ext_data.price_amount)) if ext_data.price_amount is not None else None,
            currency=ext_data.currency or "INR",
            rating=Decimal(str(ext_data.rating)) if ext_data.rating is not None else None,
            review_count=ext_data.review_count,
            availability=ext_data.availability,
            normalized_brand=parsed.product_context.brand_hint,
            normalized_model_name=parsed.product_context.model_hint,
            normalized_model_number=None,
            extracted_attributes=attributes,
            validation_status=parsed.validation.status,
            identity_status=parsed.validation.identity_status,
            warnings=parsed.validation.warnings,
            errors=parsed.validation.errors,
            storage_object_key=storage_object_key,
            sha256_digest=sha256_digest,
        )

