"""API routes for querying evidence records, provenance, and historical versions."""

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.core.auth import AuthenticatedUser, get_current_user
from app.db.dependencies import get_db
from app.models.evidence import Evidence
from app.schemas.evidence import EvidenceListResponse, EvidenceResponse

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
