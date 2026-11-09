"""Administrative catalog correction endpoints."""

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.core.auth import AuthenticatedUser, require_permissions
from app.core.permissions import Permission
from app.db.dependencies import get_db
from app.models.attribute import AttributeDefinition, VariantAttributeValue
from app.models.product import Product
from app.models.variant import Variant
from app.repositories.correction_repository import CorrectionRepository
from app.repositories.operations_repository import OperationsRepository
from app.schemas.correction import (
    CatalogCorrectionResponse,
    CreateCatalogCorrectionRequest,
)

router = APIRouter(prefix="/admin/corrections", tags=["Administrative Corrections"])


@router.post(
    "",
    response_model=CatalogCorrectionResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Record catalog correction",
    description="Record an administrative catalog correction with auditable before/after state.",
)
def record_catalog_correction(
    payload: CreateCatalogCorrectionRequest,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[
        AuthenticatedUser, Depends(require_permissions(Permission.CATALOG_MANAGE))
    ],
) -> CatalogCorrectionResponse:
    """Record an administrative catalog correction."""
    # Verify target entity existence
    if payload.target_type == "variant_attribute":
        vav = db.get(VariantAttributeValue, payload.target_id)
        if not vav:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Variant attribute record not found.",
            )
    elif payload.target_type == "product":
        prod = db.get(Product, payload.target_id)
        if not prod:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Product not found."
            )
    elif payload.target_type == "variant":
        var = db.get(Variant, payload.target_id)
        if not var:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Variant not found."
            )
    elif payload.target_type == "attribute_definition":
        attr_def = db.get(AttributeDefinition, payload.target_id)
        if not attr_def:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Attribute definition not found.",
            )

    correction = CorrectionRepository.create_correction(
        db,
        target_type=payload.target_type,
        target_id=payload.target_id,
        field_name=payload.field_name,
        before_value=payload.before_value,
        after_value=payload.after_value,
        reason=payload.reason,
        actor_id=str(current_user.id),
        evidence_reference=payload.evidence_reference,
    )

    OperationsRepository.create_audit_log(
        db,
        actor_type="user",
        actor_id=str(current_user.id),
        action="admin.catalog_correction",
        target_type=payload.target_type,
        target_id=str(payload.target_id),
        status="success",
        metadata_payload={
            "field_name": payload.field_name,
            "reason": payload.reason,
        },
    )
    db.commit()

    return CatalogCorrectionResponse(
        id=correction.id,
        target_type=correction.target_type,
        target_id=correction.target_id,
        field_name=correction.field_name,
        before_value=correction.before_value,
        after_value=correction.after_value,
        reason=correction.reason,
        actor_id=correction.actor_id,
        evidence_reference=correction.evidence_reference,
        created_at=correction.created_at.isoformat(),
    )


@router.get(
    "",
    response_model=list[CatalogCorrectionResponse],
    summary="List catalog corrections",
    description="Inspect administrative catalog correction history. Restricted to catalog managers.",
)
def list_catalog_corrections(
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[
        AuthenticatedUser, Depends(require_permissions(Permission.CATALOG_MANAGE))
    ],
    target_type: Annotated[
        str | None, Query(description="Filter by target type")
    ] = None,
    target_id: Annotated[
        uuid.UUID | None, Query(description="Filter by target ID")
    ] = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> list[CatalogCorrectionResponse]:
    """List catalog corrections."""
    corrections = CorrectionRepository.list_corrections(
        db,
        target_type=target_type,
        target_id=target_id,
        limit=limit,
        offset=offset,
    )
    return [
        CatalogCorrectionResponse(
            id=c.id,
            target_type=c.target_type,
            target_id=c.target_id,
            field_name=c.field_name,
            before_value=c.before_value,
            after_value=c.after_value,
            reason=c.reason,
            actor_id=c.actor_id,
            evidence_reference=c.evidence_reference,
            created_at=c.created_at.isoformat(),
        )
        for c in corrections
    ]
