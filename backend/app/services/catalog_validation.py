"""Product and variant validation service according to Phase B5.4."""

import uuid
from dataclasses import dataclass, field
from decimal import Decimal, InvalidOperation
from typing import Any, Literal

from sqlalchemy.orm import Session

from app.core.units import UnitNormalizer
from app.models.attribute import AttributeDefinition
from app.models.product import Product
from app.models.variant import Variant

ValidationStatusType = Literal["valid", "invalid", "incomplete", "needs_review"]


@dataclass
class AttributeValidationIssue:
    """Detailed validation issue for a specific attribute."""

    attribute_key: str
    issue_type: str  # "missing_required", "type_mismatch", "range_violation", "unit_incompatible", "invalid_enum"
    message: str
    severity: Literal["error", "warning"] = "error"


@dataclass
class ValidationReport:
    """Comprehensive validation outcome for a product or variant."""

    target_id: uuid.UUID
    target_type: Literal["product", "variant"]
    status: ValidationStatusType
    is_valid: bool
    issues: list[AttributeValidationIssue] = field(default_factory=list)
    validated_attributes: dict[str, Any] = field(default_factory=dict)


class CatalogValidator:
    """Reusable validator for canonical products and variants."""

    def __init__(self, db: Session):
        self.db = db

    def validate_variant(self, variant: Variant) -> ValidationReport:
        """Validate variant against category attribute definitions, constraints, and hardware rules."""
        issues: list[AttributeValidationIssue] = []
        product = variant.product

        # Retrieve definitions applicable to this product's category
        category_id = product.category_id if product else None
        definitions = (
            self.db.query(AttributeDefinition)
            .filter(
                (AttributeDefinition.category_id == category_id)
                | (AttributeDefinition.category_id.is_(None))
            )
            .filter(AttributeDefinition.status == "active")
            .all()
        )

        def_map = {d.key: d for d in definitions}
        values_map = {
            v.attribute_definition.key: v
            for v in variant.attribute_values
            if v.attribute_definition
        }

        # 1. Check required attributes
        for key, req_def in def_map.items():
            if req_def.is_required:
                val_record = values_map.get(key)
                if not val_record or (
                    val_record.value_text is None
                    and val_record.value_numeric is None
                    and val_record.value_boolean is None
                    and val_record.value_json is None
                ):
                    issues.append(
                        AttributeValidationIssue(
                            attribute_key=key,
                            issue_type="missing_required",
                            message=f"Required attribute '{req_def.name}' ({key}) is missing.",
                            severity="error",
                        )
                    )

        # 2. Validate populated attribute values
        validated_attrs: dict[str, Any] = {}
        for key, val_record in values_map.items():
            attr_def = def_map.get(key)
            if not attr_def:
                continue

            rules = attr_def.validation_rules or {}

            # A. Check type adherence
            if attr_def.data_type == "numeric":
                if val_record.value_numeric is None and val_record.raw_value:
                    try:
                        Decimal(str(val_record.raw_value))
                    except (InvalidOperation, TypeError, ValueError):
                        issues.append(
                            AttributeValidationIssue(
                                attribute_key=key,
                                issue_type="type_mismatch",
                                message=f"Attribute '{key}' expects numeric value, got '{val_record.raw_value}'.",
                                severity="error",
                            )
                        )
                if val_record.value_numeric is not None:
                    num_val = val_record.value_numeric
                    validated_attrs[key] = num_val

                    # Range checks
                    min_val = rules.get("min")
                    if min_val is not None and num_val < Decimal(str(min_val)):
                        issues.append(
                            AttributeValidationIssue(
                                attribute_key=key,
                                issue_type="range_violation",
                                message=f"Attribute '{key}' value {num_val} is below minimum {min_val}.",
                                severity="error",
                            )
                        )
                    max_val = rules.get("max")
                    if max_val is not None and num_val > Decimal(str(max_val)):
                        issues.append(
                            AttributeValidationIssue(
                                attribute_key=key,
                                issue_type="range_violation",
                                message=f"Attribute '{key}' value {num_val} exceeds maximum {max_val}.",
                                severity="error",
                            )
                        )

            elif attr_def.data_type == "string":
                text_val = val_record.value_text
                if text_val is not None:
                    validated_attrs[key] = text_val
                    # Enum membership
                    allowed_enums = rules.get("enum")
                    if allowed_enums and text_val not in allowed_enums:
                        issues.append(
                            AttributeValidationIssue(
                                attribute_key=key,
                                issue_type="invalid_enum",
                                message=f"Attribute '{key}' value '{text_val}' not in allowed enum options: {allowed_enums}.",
                                severity="error",
                            )
                        )

            elif (
                attr_def.data_type == "boolean" and val_record.value_boolean is not None
            ):
                validated_attrs[key] = val_record.value_boolean

            # B. Validate unit dimensions if unit is specified
            if val_record.original_unit and attr_def.canonical_unit:
                conv = UnitNormalizer.normalize(
                    val_record.value_numeric,
                    val_record.original_unit,
                    target_canonical_unit=attr_def.canonical_unit,
                )
                if not conv.is_valid:
                    issues.append(
                        AttributeValidationIssue(
                            attribute_key=key,
                            issue_type="unit_incompatible",
                            message=conv.error
                            or f"Incompatible unit '{val_record.original_unit}' for canonical '{attr_def.canonical_unit}'.",
                            severity="error",
                        )
                    )

        # 3. Determine status
        errors = [i for i in issues if i.severity == "error"]
        warnings = [i for i in issues if i.severity == "warning"]

        if errors:
            has_fatal = any(
                e.issue_type in ("type_mismatch", "unit_incompatible", "invalid_enum")
                for e in errors
            )
            status: ValidationStatusType = "invalid" if has_fatal else "incomplete"
        elif warnings:
            status = "needs_review"
        else:
            status = "valid"

        return ValidationReport(
            target_id=variant.id,
            target_type="variant",
            status=status,
            is_valid=len(errors) == 0,
            issues=issues,
            validated_attributes=validated_attrs,
        )

    def validate_product(self, product: Product) -> ValidationReport:
        """Validate base product entity."""
        issues: list[AttributeValidationIssue] = []

        if not product.name or not product.name.strip():
            issues.append(
                AttributeValidationIssue(
                    attribute_key="name",
                    issue_type="missing_required",
                    message="Product name is required.",
                    severity="error",
                )
            )

        if not product.manufacturer or not product.manufacturer.strip():
            issues.append(
                AttributeValidationIssue(
                    attribute_key="manufacturer",
                    issue_type="missing_required",
                    message="Product manufacturer/brand is required.",
                    severity="error",
                )
            )

        status: ValidationStatusType = "invalid" if issues else "valid"
        return ValidationReport(
            target_id=product.id,
            target_type="product",
            status=status,
            is_valid=len(issues) == 0,
            issues=issues,
        )
