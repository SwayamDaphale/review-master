"""Catalog attribute repository for schema definitions and normalized variant values."""

import uuid
from decimal import Decimal
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload

from app.core.units import UnitNormalizer
from app.models.attribute import AttributeDefinition, VariantAttributeValue


class AttributeRepository:
    """Repository managing attribute definitions and variant attribute assignments."""

    @staticmethod
    def create_definition(
        db: Session,
        *,
        key: str,
        name: str,
        category_id: uuid.UUID | None = None,
        data_type: str = "string",
        unit: str | None = None,
        canonical_unit: str | None = None,
        validation_rules: dict[str, Any] | None = None,
        is_required: bool = False,
        is_filterable: bool = True,
        is_searchable: bool = False,
        status: str = "active",
    ) -> AttributeDefinition:
        """Create and persist an attribute definition."""
        attr_def = AttributeDefinition(
            key=key,
            name=name,
            category_id=category_id,
            data_type=data_type,
            unit=unit,
            canonical_unit=canonical_unit or unit,
            validation_rules=validation_rules or {},
            is_required=is_required,
            is_filterable=is_filterable,
            is_searchable=is_searchable,
            status=status,
        )
        db.add(attr_def)
        db.flush()
        return attr_def

    @staticmethod
    def get_definition_by_key(
        db: Session,
        key: str,
        category_id: uuid.UUID | None = None,
    ) -> AttributeDefinition | None:
        """Lookup attribute definition by key and optional category scope."""
        stmt = select(AttributeDefinition).where(AttributeDefinition.key == key)
        if category_id:
            stmt = stmt.where(AttributeDefinition.category_id == category_id)
        return db.execute(stmt).scalar_one_or_none()

    @staticmethod
    def list_definitions(
        db: Session,
        category_id: uuid.UUID | None = None,
        include_inactive: bool = False,
    ) -> list[AttributeDefinition]:
        """List attribute definitions, optionally filtered by category."""
        stmt = select(AttributeDefinition)
        if not include_inactive:
            stmt = stmt.where(AttributeDefinition.status == "active")
        if category_id:
            stmt = stmt.where(
                (AttributeDefinition.category_id == category_id)
                | (AttributeDefinition.category_id.is_(None))
            )
        stmt = stmt.order_by(AttributeDefinition.key.asc())
        return list(db.execute(stmt).scalars().all())

    @staticmethod
    def set_variant_value(
        db: Session,
        *,
        variant_id: uuid.UUID,
        attribute_id: uuid.UUID,
        value_text: str | None = None,
        value_numeric: Decimal | float | None = None,
        value_boolean: bool | None = None,
        value_json: dict[str, Any] | None = None,
        raw_value: str | None = None,
        original_unit: str | None = None,
        canonical_unit: str | None = None,
        confidence: Decimal | float | None = None,
        validation_status: str = "valid",
        evidence_id: uuid.UUID | None = None,
    ) -> VariantAttributeValue:
        """Set or update normalized attribute value for a variant with unit normalization."""
        stmt = select(VariantAttributeValue).where(
            VariantAttributeValue.variant_id == variant_id,
            VariantAttributeValue.attribute_id == attribute_id,
        )
        record = db.execute(stmt).scalar_one_or_none()

        attr_def = db.get(AttributeDefinition, attribute_id)
        target_canonical = canonical_unit or (
            attr_def.canonical_unit if attr_def else None
        )

        num_val = Decimal(str(value_numeric)) if value_numeric is not None else None
        norm_unit = original_unit or (attr_def.unit if attr_def else None)

        # Apply Unit Normalizer if numeric and units are present
        if num_val is not None and norm_unit:
            conv = UnitNormalizer.normalize(
                value=num_val,
                unit=norm_unit,
                target_canonical_unit=target_canonical,
            )
            if conv.is_valid and conv.canonical_value is not None:
                num_val = conv.canonical_value
                target_canonical = conv.canonical_unit

        conf_val = Decimal(str(confidence)) if confidence is not None else None

        if record:
            record.value_text = value_text
            record.value_numeric = num_val
            record.value_boolean = value_boolean
            record.value_json = value_json
            record.raw_value = raw_value or str(
                value_numeric if value_numeric is not None else value_text
            )
            record.original_unit = norm_unit
            record.canonical_unit = target_canonical
            record.confidence = conf_val
            record.validation_status = validation_status
            record.evidence_id = evidence_id
        else:
            record = VariantAttributeValue(
                variant_id=variant_id,
                attribute_id=attribute_id,
                value_text=value_text,
                value_numeric=num_val,
                value_boolean=value_boolean,
                value_json=value_json,
                raw_value=raw_value
                or str(value_numeric if value_numeric is not None else value_text),
                original_unit=norm_unit,
                canonical_unit=target_canonical,
                confidence=conf_val,
                validation_status=validation_status,
                evidence_id=evidence_id,
            )
            db.add(record)

        db.flush()
        return record

    @staticmethod
    def get_variant_values(
        db: Session,
        variant_id: uuid.UUID,
    ) -> list[VariantAttributeValue]:
        """Retrieve all normalized attribute values for a given variant."""
        stmt = (
            select(VariantAttributeValue)
            .where(VariantAttributeValue.variant_id == variant_id)
            .options(joinedload(VariantAttributeValue.attribute_definition))
        )
        return list(db.execute(stmt).scalars().all())
