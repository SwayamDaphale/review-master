"""Requirement-based recommendation API endpoints."""

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.auth import AuthenticatedUser, require_permissions
from app.core.permissions import Permission
from app.db.dependencies import get_db
from app.schemas.recommendation import (
    RecommendationRequest,
    RecommendationResponse,
    RequirementParseRequest,
    RequirementParseResponse,
)
from app.services.recommendation_service import RecommendationService
from app.services.requirement_parser import RequirementParserService

router = APIRouter(prefix="/recommendations", tags=["Recommendations"])


@router.post(
    "/parse",
    response_model=RequirementParseResponse,
    status_code=status.HTTP_200_OK,
    summary="Parse natural language requirements",
    description="Extracts structured constraints and preferences from user text using approved LLM or deterministic fallback.",
)
def parse_requirements(
    payload: RequirementParseRequest,
    current_user: Annotated[
        AuthenticatedUser, Depends(require_permissions(Permission.CATALOG_READ))
    ],
) -> RequirementParseResponse:
    """Parse natural language query."""
    parser = RequirementParserService()
    return parser.parse_query(payload.query, category_hint=payload.category_hint)


@router.post(
    "",
    response_model=RecommendationResponse,
    status_code=status.HTTP_200_OK,
    summary="Generate requirement-based product recommendations",
    description="Filters catalog products via deterministic three-valued hard constraints (PASS/FAIL/UNKNOWN), ranks eligible candidates using B9 evaluation scores, and produces traceable explanations.",
)
def generate_recommendations(
    payload: RecommendationRequest,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[
        AuthenticatedUser, Depends(require_permissions(Permission.CATALOG_READ))
    ],
) -> RecommendationResponse:
    """Generate recommendations based on requirements."""
    user_uuid = None
    try:
        user_uuid = uuid.UUID(current_user.id)
    except ValueError:
        pass

    service = RecommendationService(db)
    try:
        return service.generate_recommendations(payload, user_id=user_uuid)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        )


@router.get(
    "/{recommendation_id}",
    response_model=RecommendationResponse,
    status_code=status.HTTP_200_OK,
    summary="Retrieve historical recommendation run",
    description="Fetches an immutable historical recommendation run with full audit trail and candidate exclusion reasons.",
)
def get_recommendation(
    recommendation_id: uuid.UUID,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[
        AuthenticatedUser, Depends(require_permissions(Permission.CATALOG_READ))
    ],
) -> RecommendationResponse:
    """Fetch recommendation by ID."""
    service = RecommendationService(db)
    result = service.get_recommendation(recommendation_id)
    if not result:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Recommendation record '{recommendation_id}' not found.",
        )
    return result

