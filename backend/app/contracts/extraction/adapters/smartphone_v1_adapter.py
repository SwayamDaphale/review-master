"""Adapter translating Frozen Smartphone V1 payloads to CanonicalInternalExtraction."""

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
from app.contracts.extraction.smartphone_v1 import SmartphoneExtractionV1Payload
from app.schemas.contract_validator import assert_valid_contract_payload


class SmartphoneExtractionV1Adapter(ExtractionContractAdapter):
    """Adapter for the approved frozen smartphone-extraction-1.0.schema.json contract."""

    @property
    def contract_name(self) -> str:
        return "smartphone_extraction"

    @property
    def supported_versions(self) -> set[str]:
        return {"1.0", "1.0.0"}

    def validate(self, payload: dict[str, Any]) -> None:
        """Validate against frozen JSON Schema Draft 2020-12 and strict Pydantic model."""
        # 1. First validate with JSON Schema validator (normalizing 1.0.0 alias for draft validator if needed)
        schema_ver = payload.get("schema_version")
        if schema_ver not in self.supported_versions:
            raise ContractValidationError(
                f"Unsupported schema version '{schema_ver}'. Expected '1.0' or '1.0.0'.",
                errors=[{"loc": ["schema_version"], "code": "unsupported_version", "msg": f"Expected 1.0 or 1.0.0, got '{schema_ver}'"}],
            )

        # For strict JSON schema checking, temporarily validate with 1.0 if passed as 1.0.0
        js_payload = payload
        if schema_ver == "1.0.0":
            js_payload = dict(payload)
            js_payload["schema_version"] = "1.0"

        try:
            assert_valid_contract_payload(js_payload)
        except Exception as e:
            err_list = getattr(e, "errors", [{"loc": ["payload"], "code": "schema_violation", "msg": str(e)}])
            raise ContractValidationError(
                f"Payload violated frozen smartphone extraction contract: {e}",
                errors=err_list,
            ) from e

        # 2. Validate with Pydantic v2 model
        try:
            SmartphoneExtractionV1Payload.model_validate(payload)
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
                f"Validation error in smartphone payload: {e}",
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
        """Convert validated smartphone payload into CanonicalInternalExtraction."""
        self.validate(payload)
        parsed = SmartphoneExtractionV1Payload.model_validate(payload)

        # Map smartphone normalized specs to category-independent CanonicalExtractedAttribute list
        attributes: list[CanonicalExtractedAttribute] = []
        norm = parsed.normalized

        if norm.ram_gb is not None:
            attributes.append(
                CanonicalExtractedAttribute(
                    attribute_key="ram",
                    value_type="numeric",
                    value=norm.ram_gb,
                    original_value=str(norm.ram_gb),
                    original_unit="GB",
                    normalized_value=norm.ram_gb,
                    normalized_unit="GB",
                    confidence=Decimal("1.0"),
                    source_reference="normalized.ram_gb",
                )
            )

        if norm.storage_gb is not None:
            attributes.append(
                CanonicalExtractedAttribute(
                    attribute_key="storage",
                    value_type="numeric",
                    value=norm.storage_gb,
                    original_value=str(norm.storage_gb),
                    original_unit="GB",
                    normalized_value=norm.storage_gb,
                    normalized_unit="GB",
                    confidence=Decimal("1.0"),
                    source_reference="normalized.storage_gb",
                )
            )

        if norm.display_size_inches is not None:
            attributes.append(
                CanonicalExtractedAttribute(
                    attribute_key="display_size",
                    value_type="numeric",
                    value=norm.display_size_inches,
                    original_value=str(norm.display_size_inches),
                    original_unit="inch",
                    normalized_value=norm.display_size_inches,
                    normalized_unit="inch",
                    confidence=Decimal("1.0"),
                    source_reference="normalized.display_size_inches",
                )
            )

        if norm.battery_capacity_mah is not None:
            attributes.append(
                CanonicalExtractedAttribute(
                    attribute_key="battery",
                    value_type="numeric",
                    value=norm.battery_capacity_mah,
                    original_value=str(norm.battery_capacity_mah),
                    original_unit="mAh",
                    normalized_value=norm.battery_capacity_mah,
                    normalized_unit="mAh",
                    confidence=Decimal("1.0"),
                    source_reference="normalized.battery_capacity_mah",
                )
            )

        if norm.operating_system is not None:
            attributes.append(
                CanonicalExtractedAttribute(
                    attribute_key="operating_system",
                    value_type="string",
                    value=norm.operating_system,
                    original_value=norm.operating_system,
                    normalized_value=norm.operating_system,
                    confidence=Decimal("1.0"),
                    source_reference="normalized.operating_system",
                )
            )

        if norm.processor is not None:
            attributes.append(
                CanonicalExtractedAttribute(
                    attribute_key="processor",
                    value_type="string",
                    value=norm.processor,
                    original_value=norm.processor,
                    normalized_value=norm.processor,
                    confidence=Decimal("1.0"),
                    source_reference="normalized.processor",
                )
            )

        if norm.supports_5g is not None:
            attributes.append(
                CanonicalExtractedAttribute(
                    attribute_key="supports_5g",
                    value_type="boolean",
                    value=norm.supports_5g,
                    original_value=str(norm.supports_5g),
                    normalized_value=norm.supports_5g,
                    confidence=Decimal("1.0"),
                    source_reference="normalized.supports_5g",
                )
            )

        raw_specs = [
            {"label": item.label, "value": item.value}
            for item in parsed.raw_extraction.specifications_text
        ]

        resolved_rec_id = record_id or parsed.record_id or str(uuid.uuid4())

        return CanonicalInternalExtraction(
            ingestion_record_id=resolved_rec_id,
            source_contract=self.contract_name,
            source_schema_version=parsed.schema_version,
            marketplace=parsed.source.marketplace,
            page_type="product_detail",
            product_category=parsed.normalized.category,
            product_url=parsed.source.product_url,
            extraction_method=parsed.source.extraction_method,
            extension_version=parsed.source.extension_version,
            extracted_at=parsed.source.extracted_at,
            asin=parsed.source.asin,
            page_title=parsed.source.page_title,
            raw_title=parsed.raw_extraction.title,
            raw_brand=parsed.raw_extraction.brand_text,
            raw_model=parsed.raw_extraction.model_text,
            raw_variant=parsed.raw_extraction.variant_text,
            raw_price_text=parsed.raw_extraction.price_text,
            raw_rating_text=parsed.raw_extraction.rating_text,
            raw_review_count_text=parsed.raw_extraction.review_count_text,
            raw_availability_text=parsed.raw_extraction.availability_text,
            raw_specifications=raw_specs,
            price_amount=Decimal(str(norm.price_amount)) if norm.price_amount is not None else None,
            currency=norm.currency or "INR",
            rating=Decimal(str(norm.rating)) if norm.rating is not None else None,
            review_count=norm.review_count,
            availability=norm.availability,
            normalized_brand=norm.brand,
            normalized_model_name=norm.model_name,
            normalized_model_number=norm.model_number,
            extracted_attributes=attributes,
            validation_status=parsed.validation.status,
            identity_status=parsed.validation.identity_status,
            warnings=parsed.validation.warnings,
            errors=parsed.validation.errors,
            storage_object_key=storage_object_key,
            sha256_digest=sha256_digest,
        )

