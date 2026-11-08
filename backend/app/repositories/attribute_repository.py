"""Catalog attribute repository for schema definitions and normalized variant values."""

import uuid
from decimal import Decimal
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload

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
        is_filterable: bool = True,
        is_searchable: bool = False,
    ) -> AttributeDefinition:
        """Create and persist an attribute definition."""
        attr_def = AttributeDefinition(
            key=key,
            name=name,
            category_id=category_id,
            data_type=data_type,
            unit=unit,
            is_filterable=is_filterable,
            is_searchable=is_searchable,
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
    ) -> list[AttributeDefinition]:
        """List attribute definitions, optionally filtered by category."""
        stmt = select(AttributeDefinition)
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
    ) -> VariantAttributeValue:
        """Set or update normalized attribute value for a variant."""
        stmt = select(VariantAttributeValue).where(
            VariantAttributeValue.variant_id == variant_id,
            VariantAttributeValue.attribute_id == attribute_id,
        )
        record = db.execute(stmt).scalar_one_or_none()

        num_val = Decimal(str(value_numeric)) if value_numeric is not None else None

        if record:
            record.value_text = value_text
            record.value_numeric = num_val
            record.value_boolean = value_boolean
            record.value_json = value_json
            record.raw_value = raw_value
        else:
            record = VariantAttributeValue(
                variant_id=variant_id,
                attribute_id=attribute_id,
                value_text=value_text,
                value_numeric=num_val,
                value_boolean=value_boolean,
                value_json=value_json,
                raw_value=raw_value,
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
