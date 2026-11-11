"""API routes for canonical identity resolution, external mappings, and review queues."""

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.auth import AuthenticatedUser, get_current_user, require_permissions
from app.core.permissions import Permission
from app.db.base import utc_now
from app.db.dependencies import get_db
from app.models.identity_mapping import ExternalIdentityMapping, IdentityReviewQueue
from app.models.marketplace import Marketplace
from app.models.product import Product
from app.models.variant import Variant
from app.schemas.extraction import NormalizedSmartphone
from app.schemas.identity import (
    ExternalIdentityMappingCreate,
    ExternalIdentityMappingListResponse,
    ExternalIdentityMappingResponse,
    IdentityResolveRequest,
    IdentityResolveResponse,
    IdentityReviewApproveRequest,
    IdentityReviewQueueListResponse,
    IdentityReviewQueueResponse,
    IdentityReviewRejectRequest,
)
from app.services.identity_resolver import IdentityResolver

router = APIRouter(prefix="/identity", tags=["Identity Resolution"])


@router.post(
    "/resolve",
    response_model=IdentityResolveResponse,
    status_code=status.HTTP_200_OK,
    summary="Resolve canonical identity",
    description="Execute deterministic 5-stage identity resolution for a listing or extraction payload.",
)
def resolve_identity(
    payload: IdentityResolveRequest,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[AuthenticatedUser, Depends(get_current_user)],
) -> IdentityResolveResponse:
    """Resolve canonical product and variant from listing signals."""
    mp = db.execute(
        select(Marketplace).where(Marketplace.key == payload.marketplace_code)
    ).scalar_one_or_none()
    if not mp:
        mp = Marketplace(
            key=payload.marketplace_code,
            name=payload.marketplace_code.capitalize(),
            adapter="generic",
        )
        db.add(mp)
        db.flush()

    norm = NormalizedSmartphone(
        category="smartphone",
        brand=payload.brand,
        model_name=payload.model_name,
        model_number=payload.model_number,
        ram_gb=payload.ram_gb,
        storage_gb=payload.storage_gb,
    )

    resolver = IdentityResolver(db)
    resolution = resolver.resolve_smartphone(
        marketplace_id=mp.id,
        asin=payload.asin,
        normalized=norm,
        raw_title=payload.title,
    )
    db.commit()

    return IdentityResolveResponse(
        match_state=resolution.match_state,
        confidence=resolution.confidence,
        product_id=resolution.product_id,
        variant_id=resolution.variant_id,
        product_name=resolution.product_name,
        variant_label=resolution.variant_label,
        reasons=resolution.reasons,
        review_queue_id=resolution.review_queue_id,
        candidate_scores=resolution.candidate_scores,
        product_fingerprint=resolution.product_fingerprint,
        variant_fingerprint=resolution.variant_fingerprint,
    )


@router.get(
    "/mappings",
    response_model=ExternalIdentityMappingListResponse,
    status_code=status.HTTP_200_OK,
    summary="Query external identity mappings",
)
def list_mappings(
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[AuthenticatedUser, Depends(get_current_user)],
    marketplace_id: Annotated[uuid.UUID | None, Query()] = None,
    external_id_value: Annotated[str | None, Query()] = None,
    product_id: Annotated[uuid.UUID | None, Query()] = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
) -> ExternalIdentityMappingListResponse:
    """List external identity mappings with optional filters."""
    stmt = select(ExternalIdentityMapping)
    if marketplace_id:
        stmt = stmt.where(ExternalIdentityMapping.marketplace_id == marketplace_id)
    if external_id_value:
        stmt = stmt.where(ExternalIdentityMapping.external_id_value == external_id_value)
    if product_id:
        stmt = stmt.where(ExternalIdentityMapping.product_id == product_id)

    stmt = stmt.limit(limit)
    items = db.execute(stmt).scalars().all()
    return ExternalIdentityMappingListResponse(
        total=len(items),
        items=[ExternalIdentityMappingResponse.model_validate(m) for m in items],
    )


@router.post(
    "/mappings",
    response_model=ExternalIdentityMappingResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create or link external identity mapping",
)
def create_mapping(
    payload: ExternalIdentityMappingCreate,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[
        AuthenticatedUser, Depends(require_permissions(Permission.CATALOG_MANAGE))
    ],
) -> ExternalIdentityMappingResponse:
    """Create or register an authoritative external identity mapping."""
    # Check if mapping already exists
    existing = db.execute(
        select(ExternalIdentityMapping).where(
            ExternalIdentityMapping.marketplace_id == payload.marketplace_id,
            ExternalIdentityMapping.external_id_type == payload.external_id_type,
            ExternalIdentityMapping.external_id_value == payload.external_id_value,
        )
    ).scalar_one_or_none()

    if existing:
        existing.product_id = payload.product_id
        existing.variant_id = payload.variant_id
        existing.mapping_status = payload.mapping_status
        existing.verification_status = payload.verification_status
        existing.confidence_score = payload.confidence_score
        existing.provenance = payload.provenance
        db.commit()
        db.refresh(existing)
        return ExternalIdentityMappingResponse.model_validate(existing)

    mapping = ExternalIdentityMapping(
        marketplace_id=payload.marketplace_id,
        external_id_type=payload.external_id_type,
        external_id_value=payload.external_id_value,
        product_id=payload.product_id,
        variant_id=payload.variant_id,
        mapping_status=payload.mapping_status,
        verification_status=payload.verification_status,
        confidence_score=payload.confidence_score,
        provenance=payload.provenance,
    )
    db.add(mapping)
    db.commit()
    db.refresh(mapping)
    return ExternalIdentityMappingResponse.model_validate(mapping)


@router.get(
    "/reviews",
    response_model=IdentityReviewQueueListResponse,
    status_code=status.HTTP_200_OK,
    summary="List identity review queue items",
)
def list_review_queue(
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[
        AuthenticatedUser, Depends(require_permissions(Permission.CATALOG_READ))
    ],
    status_filter: Annotated[str | None, Query(alias="status")] = None,
    asin: Annotated[str | None, Query()] = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
) -> IdentityReviewQueueListResponse:
    """List review queue items with optional status filtering."""
    stmt = select(IdentityReviewQueue)
    if status_filter:
        stmt = stmt.where(IdentityReviewQueue.status == status_filter)
    if asin:
        stmt = stmt.where(IdentityReviewQueue.asin == asin)

    stmt = stmt.order_by(IdentityReviewQueue.created_at.desc()).limit(limit)
    items = db.execute(stmt).scalars().all()
    return IdentityReviewQueueListResponse(
        total=len(items),
        items=[IdentityReviewQueueResponse.model_validate(i) for i in items],
    )


@router.get(
    "/reviews/{review_id}",
    response_model=IdentityReviewQueueResponse,
    status_code=status.HTTP_200_OK,
    summary="Get identity review item details",
)
def get_review_item(
    review_id: uuid.UUID,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[
        AuthenticatedUser, Depends(require_permissions(Permission.CATALOG_READ))
    ],
) -> IdentityReviewQueueResponse:
    """Retrieve details of a specific review queue entry."""
    item = db.get(IdentityReviewQueue, review_id)
    if not item:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Identity review queue item {review_id} not found.",
        )
    return IdentityReviewQueueResponse.model_validate(item)


@router.post(
    "/reviews/{review_id}/approve",
    response_model=IdentityReviewQueueResponse,
    status_code=status.HTTP_200_OK,
    summary="Approve identity review item",
)
def approve_review_item(
    review_id: uuid.UUID,
    payload: IdentityReviewApproveRequest,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[
        AuthenticatedUser, Depends(require_permissions(Permission.CATALOG_MANAGE))
    ],
) -> IdentityReviewQueueResponse:
    """Approve candidate linkage and create authoritative external mapping."""
    item = db.get(IdentityReviewQueue, review_id)
    if not item:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Identity review queue item {review_id} not found.",
        )

    if payload.product_id:
        prod = db.get(Product, payload.product_id)
        if not prod:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Product {payload.product_id} not found.",
            )

    if payload.variant_id:
        var = db.get(Variant, payload.variant_id)
        if not var:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Variant {payload.variant_id} not found.",
            )

    user_uuid = uuid.UUID(current_user.id) if current_user.id else None
    item.status = "approved"
    item.reviewer_decision = payload.decision
    item.decision_reason = payload.reason
    item.assigned_reviewer_id = user_uuid
    item.resolved_at = utc_now()

    # Create authoritative ExternalIdentityMapping if marketplace and asin exist
    if item.marketplace_id and item.asin:
        ext_mapping = db.execute(
            select(ExternalIdentityMapping).where(
                ExternalIdentityMapping.marketplace_id == item.marketplace_id,
                ExternalIdentityMapping.external_id_type == "asin",
                ExternalIdentityMapping.external_id_value == item.asin,
            )
        ).scalar_one_or_none()

        if ext_mapping:
            ext_mapping.product_id = payload.product_id
            ext_mapping.variant_id = payload.variant_id
            ext_mapping.mapping_status = "active"
            ext_mapping.verification_status = "verified"
            ext_mapping.confidence_score = 1.0
        else:
            ext_mapping = ExternalIdentityMapping(
                marketplace_id=item.marketplace_id,
                external_id_type="asin",
                external_id_value=item.asin,
                product_id=payload.product_id,
                variant_id=payload.variant_id,
                mapping_status="active",
                verification_status="verified",
                confidence_score=1.0,
                provenance={
                    "approved_by": str(current_user.id),
                    "review_id": str(item.id),
                    "reason": payload.reason,
                },
            )
            db.add(ext_mapping)

    db.commit()
    db.refresh(item)
    return IdentityReviewQueueResponse.model_validate(item)


@router.post(
    "/reviews/{review_id}/reject",
    response_model=IdentityReviewQueueResponse,
    status_code=status.HTTP_200_OK,
    summary="Reject identity review item",
)
def reject_review_item(
    review_id: uuid.UUID,
    payload: IdentityReviewRejectRequest,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[
        AuthenticatedUser, Depends(require_permissions(Permission.CATALOG_MANAGE))
    ],
) -> IdentityReviewQueueResponse:
    """Reject candidate linkage for an identity review item."""
    item = db.get(IdentityReviewQueue, review_id)
    if not item:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Identity review queue item {review_id} not found.",
        )

    user_uuid = uuid.UUID(current_user.id) if current_user.id else None
    item.status = "rejected"
    item.reviewer_decision = "reject"
    item.decision_reason = payload.reason
    item.assigned_reviewer_id = user_uuid
    item.resolved_at = utc_now()

    db.commit()
    db.refresh(item)
    return IdentityReviewQueueResponse.model_validate(item)
