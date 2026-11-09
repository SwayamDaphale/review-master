"""Catalog intelligence, attribute registry, and specification search endpoints."""

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.auth import AuthenticatedUser, require_permissions
from app.core.permissions import Permission
from app.db.dependencies import get_db
from app.models.attribute import AttributeDefinition
from app.models.unit import UnitDefinition
from app.models.variant import Variant
from app.repositories.attribute_repository import AttributeRepository
from app.schemas.catalog_intelligence import (
    AttributeDefinitionCreate,
    AttributeDefinitionResponse,
    SearchProductResult,
    SearchVariantItem,
    SetVariantAttributeRequest,
    SpecificationSearchRequest,
    SpecificationSearchResponse,
    UnitResponse,
    ValidationIssueResponse,
    ValidationResponse,
    VariantAttributeValueResponse,
)
from app.services.catalog_search import CatalogSearchService, SearchFilters
from app.services.catalog_validation import CatalogValidator

router = APIRouter(prefix="/catalog", tags=["Catalog Intelligence"])


@router.get(
    "/units",
    response_model=list[UnitResponse],
    summary="List domain units",
    description="Retrieve supported physical measurement units with conversion metadata.",
)
def list_units(
    db: Annotated[Session, Depends(get_db)],
) -> list[UnitResponse]:
    """List all registered domain units."""
    stmt = (
        select(UnitDefinition)
        .where(UnitDefinition.is_active.is_(True))
        .order_by(UnitDefinition.dimension, UnitDefinition.key)
    )
    units = list(db.execute(stmt).scalars().all())
    return [
        UnitResponse(
            key=u.key,
            name=u.name,
            symbol=u.symbol,
            dimension=u.dimension,
            canonical_unit=u.canonical_unit,
            conversion_factor=u.conversion_factor,
            is_binary=u.is_binary,
            is_active=u.is_active,
        )
        for u in units
    ]


@router.get(
    "/attributes",
    response_model=list[AttributeDefinitionResponse],
    summary="List attribute definitions",
    description="Retrieve category-independent attribute definitions with validation rules.",
)
def list_attributes(
    db: Annotated[Session, Depends(get_db)],
    category_id: Annotated[
        uuid.UUID | None, Query(description="Optional category scope")
    ] = None,
) -> list[AttributeDefinitionResponse]:
    """List active attribute definitions."""
    defs = AttributeRepository.list_definitions(db, category_id=category_id)
    return [
        AttributeDefinitionResponse(
            id=d.id,
            key=d.key,
            name=d.name,
            category_id=d.category_id,
            data_type=d.data_type,
            unit=d.unit,
            canonical_unit=d.canonical_unit,
            validation_rules=d.validation_rules or {},
            is_required=d.is_required,
            is_filterable=d.is_filterable,
            is_searchable=d.is_searchable,
            status=d.status,
        )
        for d in defs
    ]


@router.post(
    "/attributes",
    response_model=AttributeDefinitionResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create attribute definition",
    description="Register a new specification attribute schema. Restricted to catalog managers.",
)
def create_attribute_definition(
    payload: AttributeDefinitionCreate,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[
        AuthenticatedUser, Depends(require_permissions(Permission.CATALOG_MANAGE))
    ],
) -> AttributeDefinitionResponse:
    """Create a new attribute definition."""
    existing = AttributeRepository.get_definition_by_key(
        db, payload.key, category_id=payload.category_id
    )
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Attribute definition with key '{payload.key}' already exists for this category scope.",
        )

    d = AttributeRepository.create_definition(
        db,
        key=payload.key,
        name=payload.name,
        category_id=payload.category_id,
        data_type=payload.data_type,
        unit=payload.unit,
        canonical_unit=payload.canonical_unit,
        validation_rules=payload.validation_rules,
        is_required=payload.is_required,
        is_filterable=payload.is_filterable,
        is_searchable=payload.is_searchable,
    )
    db.commit()

    return AttributeDefinitionResponse(
        id=d.id,
        key=d.key,
        name=d.name,
        category_id=d.category_id,
        data_type=d.data_type,
        unit=d.unit,
        canonical_unit=d.canonical_unit,
        validation_rules=d.validation_rules or {},
        is_required=d.is_required,
        is_filterable=d.is_filterable,
        is_searchable=d.is_searchable,
        status=d.status,
    )


@router.post(
    "/variants/{variant_id}/attributes",
    response_model=VariantAttributeValueResponse,
    status_code=status.HTTP_200_OK,
    summary="Set variant attribute value",
    description="Assign normalized attribute value to a variant with automatic unit conversion.",
)
def set_variant_attribute_value(
    variant_id: uuid.UUID,
    payload: SetVariantAttributeRequest,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[
        AuthenticatedUser, Depends(require_permissions(Permission.CATALOG_MANAGE))
    ],
) -> VariantAttributeValueResponse:
    """Set variant attribute value."""
    variant = db.get(Variant, variant_id)
    if not variant:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Variant not found."
        )

    attr_def = db.get(AttributeDefinition, payload.attribute_id)
    if not attr_def:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Attribute definition not found.",
        )

    vav = AttributeRepository.set_variant_value(
        db,
        variant_id=variant_id,
        attribute_id=payload.attribute_id,
        value_text=payload.value_text,
        value_numeric=payload.value_numeric,
        value_boolean=payload.value_boolean,
        value_json=payload.value_json,
        original_unit=payload.original_unit,
        canonical_unit=payload.canonical_unit,
        confidence=payload.confidence,
        evidence_id=payload.evidence_id,
    )
    db.commit()

    return VariantAttributeValueResponse(
        id=vav.id,
        variant_id=vav.variant_id,
        attribute_id=vav.attribute_id,
        attribute_key=attr_def.key,
        attribute_name=attr_def.name,
        value_text=vav.value_text,
        value_numeric=vav.value_numeric,
        value_boolean=vav.value_boolean,
        value_json=vav.value_json,
        raw_value=vav.raw_value,
        original_unit=vav.original_unit,
        canonical_unit=vav.canonical_unit,
        confidence=vav.confidence,
        validation_status=vav.validation_status,
    )


@router.post(
    "/search",
    response_model=SpecificationSearchResponse,
    summary="Specification-aware catalog search",
    description="Search products and variants matching category, brand, query, and numeric specification filters.",
)
def search_catalog(
    payload: SpecificationSearchRequest,
    db: Annotated[Session, Depends(get_db)],
) -> SpecificationSearchResponse:
    """Execute specification search."""
    search_service = CatalogSearchService(db)
    filters = SearchFilters(
        category_key=payload.category_key,
        brand=payload.brand,
        query=payload.query,
        min_ram_gb=payload.min_ram_gb,
        max_ram_gb=payload.max_ram_gb,
        min_storage_gb=payload.min_storage_gb,
        max_storage_gb=payload.max_storage_gb,
        min_display_inch=payload.min_display_inch,
        max_display_inch=payload.max_display_inch,
        limit=payload.limit,
        offset=payload.offset,
    )
    items, total = search_service.search(filters)
    return SpecificationSearchResponse(
        total=total,
        items=[
            SearchProductResult(
                product_id=item.product_id,
                product_name=item.product_name,
                manufacturer=item.manufacturer,
                category_key=item.category_key,
                generation=item.generation,
                variants=[SearchVariantItem(**v) for v in item.variants],
            )
            for item in items
        ],
        limit=payload.limit,
        offset=payload.offset,
    )


@router.post(
    "/validate/variant/{variant_id}",
    response_model=ValidationResponse,
    summary="Validate variant attributes",
    description="Run validation rules against a variant's attributes.",
)
def validate_variant_endpoint(
    variant_id: uuid.UUID,
    db: Annotated[Session, Depends(get_db)],
) -> ValidationResponse:
    """Validate variant attributes."""
    variant = db.get(Variant, variant_id)
    if not variant:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Variant not found."
        )

    validator = CatalogValidator(db)
    report = validator.validate_variant(variant)
    return ValidationResponse(
        target_id=report.target_id,
        target_type=report.target_type,
        status=report.status,
        is_valid=report.is_valid,
        issues=[
            ValidationIssueResponse(
                attribute_key=i.attribute_key,
                issue_type=i.issue_type,
                message=i.message,
                severity=i.severity,
            )
            for i in report.issues
        ],
        validated_attributes={
            k: str(v) for k, v in report.validated_attributes.items()
        },
    )
