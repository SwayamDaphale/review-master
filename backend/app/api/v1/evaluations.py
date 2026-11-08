"""API endpoints for deterministic product evaluation foundation."""

import uuid
from decimal import Decimal
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, ConfigDict
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.core.auth import AuthenticatedUser, require_permissions
from app.core.permissions import Permission
from app.db.dependencies import get_db
from app.models.evaluation import Evaluation
from app.services.evaluation_service import EvaluationFoundationService

router = APIRouter(tags=["Evaluations"])


class ParameterResultResponse(BaseModel):
    """Parameter-level score outcome."""

    model_config = ConfigDict(from_attributes=True)

    parameter_key: str
    score: Decimal | None = None
    status: str
    weight: Decimal | None = None
    is_critical: bool
    evidence_ids: list[str] = []
    explanation_data: dict[str, Any] | None = None


class EvaluationResponse(BaseModel):
    """Deterministic evaluation outcome envelope."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    variant_id: uuid.UUID
    model_version_id: uuid.UUID | None = None
    overall_score: Decimal | None = None
    confidence_state: str
    confidence_score: Decimal | None = None
    coverage: Decimal | None = None
    limitations: dict[str, Any] | None = None
    evidence_snapshot_hash: str | None = None
    parameter_results: list[ParameterResultResponse] = []


@router.post(
    "/variants/{variant_id}/evaluations",
    response_model=EvaluationResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Evaluate canonical variant using deterministic engine foundation",
    description="Prepares verified evidence inputs and evaluates the variant. Returns overall_score=null and confidence_state=unavailable if model is draft or evidence is incomplete.",
)
def evaluate_variant(
    variant_id: uuid.UUID,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[
        AuthenticatedUser, Depends(require_permissions(Permission.EVALUATION_MANAGE))
    ],
) -> EvaluationResponse:
    """Trigger deterministic evaluation foundation for a variant."""
    service = EvaluationFoundationService(db)
    try:
        evaluation = service.evaluate_variant(variant_id)
    except ValueError as err:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(err),
        )

    return EvaluationResponse.model_validate(evaluation)


@router.get(
    "/variants/{variant_id}/evaluations/latest",
    response_model=EvaluationResponse,
    status_code=status.HTTP_200_OK,
    summary="Get latest evaluation outcome for a canonical variant",
    description="Retrieves the most recent deterministic evaluation result for a variant.",
)
def get_latest_evaluation(
    variant_id: uuid.UUID,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[
        AuthenticatedUser, Depends(require_permissions(Permission.EVALUATION_READ))
    ],
) -> EvaluationResponse:
    """Retrieve the latest evaluation for a variant."""
    evaluation = (
        db.execute(
            select(Evaluation)
            .where(Evaluation.variant_id == variant_id)
            .order_by(Evaluation.created_at.desc())
            .options(selectinload(Evaluation.parameter_results))
        )
        .scalars()
        .first()
    )

    if not evaluation:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No evaluation found for variant '{variant_id}'.",
        )

    return EvaluationResponse.model_validate(evaluation)
