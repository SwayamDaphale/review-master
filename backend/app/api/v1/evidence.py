"""API routes for querying evidence records, provenance, conflicts, and verification."""

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.core.auth import AuthenticatedUser, get_current_user, require_permissions
from app.core.permissions import Permission
from app.db.dependencies import get_db
from app.models.evidence import Evidence
from app.models.evidence_quality import EvidenceConflict, EvidenceVerificationHistory
from app.schemas.evidence import (
    EvidenceConflictListResponse,
    EvidenceConflictResolveRequest,
    EvidenceConflictResponse,
    EvidenceListResponse,
    EvidenceResponse,
    EvidenceVerificationHistoryListResponse,
    EvidenceVerificationHistoryResponse,
    EvidenceVerifyRequest,
    EvidenceVersionResponse,
)
from app.services.evidence_service import EvidenceService

router = APIRouter(prefix="/evidence", tags=["Evidence"])


@router.get(
    "",
    response_model=EvidenceListResponse,
    status_code=status.HTTP_200_OK,
    summary="Query evidence records and provenance",
    description="Retrieve technical and commercial evidence with historical versions, trust classification, and source provenance.",
)
def list_evidence(
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[AuthenticatedUser, Depends(get_current_user)],
    variant_id: Annotated[
        uuid.UUID | None, Query(description="Filter evidence by canonical variant ID")
    ] = None,
    product_id: Annotated[
        uuid.UUID | None, Query(description="Filter evidence by canonical product ID")
    ] = None,
    parameter_key: Annotated[
        str | None,
        Query(
            description="Filter by parameter key (e.g., ram_gb, battery_capacity_mah)"
        ),
    ] = None,
    limit: Annotated[
        int, Query(ge=1, le=100, description="Maximum evidence items to return")
    ] = 50,
) -> EvidenceListResponse:
    """Retrieve evidence records matching query filters."""
    stmt = select(Evidence).options(selectinload(Evidence.versions))

    if variant_id:
        stmt = stmt.where(Evidence.variant_id == variant_id)
    if product_id:
        stmt = stmt.where(Evidence.product_id == product_id)
    if parameter_key:
        stmt = stmt.where(Evidence.parameter_key == parameter_key)

    stmt = stmt.limit(limit)
    items = db.execute(stmt).scalars().all()

    return EvidenceListResponse(
        total=len(items),
        items=[EvidenceResponse.model_validate(e) for e in items],
    )


@router.post(
    "/{evidence_id}/verify",
    response_model=EvidenceVersionResponse,
    status_code=status.HTTP_200_OK,
    summary="Update evidence verification state",
    description="Transition verification state (verified, rejected, conflicting, superseded) with mandatory audit reason.",
)
def verify_evidence(
    evidence_id: uuid.UUID,
    payload: EvidenceVerifyRequest,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[
        AuthenticatedUser, Depends(require_permissions(Permission.EVIDENCE_MANAGE))
    ],
) -> EvidenceVersionResponse:
    """Transition evidence verification state and record immutable audit history."""
    service = EvidenceService(db)
    user_uuid = uuid.UUID(current_user.id) if current_user.id else None
    try:
        updated_version = service.update_verification_state(
            evidence_id=evidence_id,
            new_status=payload.verification_state,
            actor_id=user_uuid,
            actor_role=current_user.roles[0] if current_user.roles else "reviewer",
            reason=payload.reason,
            supporting_evidence_id=payload.supporting_evidence_id,
        )
        db.commit()
        db.refresh(updated_version)
        return EvidenceVersionResponse.model_validate(updated_version)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.get(
    "/conflicts",
    response_model=EvidenceConflictListResponse,
    status_code=status.HTTP_200_OK,
    summary="List evidence conflicts",
    description="Retrieve conflicting attribute observations awaiting review or resolution.",
)
def list_conflicts(
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[
        AuthenticatedUser, Depends(require_permissions(Permission.EVIDENCE_READ))
    ],
    status_filter: Annotated[str | None, Query(alias="status")] = None,
    parameter_key: Annotated[str | None, Query()] = None,
    product_id: Annotated[uuid.UUID | None, Query()] = None,
    variant_id: Annotated[uuid.UUID | None, Query()] = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
) -> EvidenceConflictListResponse:
    """List detected evidence conflicts."""
    stmt = select(EvidenceConflict)
    if status_filter:
        stmt = stmt.where(EvidenceConflict.status == status_filter)
    if parameter_key:
        stmt = stmt.where(EvidenceConflict.parameter_key == parameter_key)
    if product_id:
        stmt = stmt.where(EvidenceConflict.product_id == product_id)
    if variant_id:
        stmt = stmt.where(EvidenceConflict.variant_id == variant_id)

    stmt = stmt.order_by(EvidenceConflict.created_at.desc()).limit(limit)
    items = db.execute(stmt).scalars().all()
    return EvidenceConflictListResponse(
        total=len(items),
        items=[EvidenceConflictResponse.model_validate(c) for c in items],
    )


@router.post(
    "/conflicts/{conflict_id}/resolve",
    response_model=EvidenceConflictResponse,
    status_code=status.HTTP_200_OK,
    summary="Resolve evidence conflict",
    description="Resolve conflicting evidence by accepting incoming, keeping existing, or superseding both.",
)
def resolve_evidence_conflict(
    conflict_id: uuid.UUID,
    payload: EvidenceConflictResolveRequest,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[
        AuthenticatedUser, Depends(require_permissions(Permission.EVIDENCE_MANAGE))
    ],
) -> EvidenceConflictResponse:
    """Resolve an open evidence conflict with audit logging."""
    service = EvidenceService(db)
    user_uuid = uuid.UUID(current_user.id) if current_user.id else None
    try:
        resolved_conflict = service.resolve_conflict(
            conflict_id=conflict_id,
            resolution_decision=payload.resolution_decision,
            resolution_reason=payload.resolution_reason,
            resolved_by=user_uuid,
        )
        db.commit()
        db.refresh(resolved_conflict)
        return EvidenceConflictResponse.model_validate(resolved_conflict)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.get(
    "/{evidence_id}/history",
    response_model=EvidenceVerificationHistoryListResponse,
    status_code=status.HTTP_200_OK,
    summary="Get evidence verification history",
    description="Retrieve chronological audit log of verification transitions for an evidence record.",
)
def get_evidence_history(
    evidence_id: uuid.UUID,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[
        AuthenticatedUser, Depends(require_permissions(Permission.EVIDENCE_READ))
    ],
) -> EvidenceVerificationHistoryListResponse:
    """Retrieve full audit history for an evidence entity."""
    stmt = (
        select(EvidenceVerificationHistory)
        .where(EvidenceVerificationHistory.evidence_id == evidence_id)
        .order_by(EvidenceVerificationHistory.created_at.asc())
    )
    items = db.execute(stmt).scalars().all()
    return EvidenceVerificationHistoryListResponse(
        total=len(items),
        items=[EvidenceVerificationHistoryResponse.model_validate(h) for h in items],
    )
