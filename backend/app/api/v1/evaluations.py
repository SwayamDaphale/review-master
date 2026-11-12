"""API endpoints for deterministic product evaluation models, versions, and calculation results."""

import uuid
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.core.auth import AuthenticatedUser, require_permissions
from app.core.permissions import Permission
from app.db.dependencies import get_db
from app.models.evaluation import Evaluation, EvaluationModel, EvaluationModelVersion
from app.schemas.evaluation import (
    EvaluationListResponse,
    EvaluationModelCreateRequest,
    EvaluationModelListResponse,
    EvaluationModelResponse,
    EvaluationModelVersionCreateRequest,
    EvaluationModelVersionResponse,
    EvaluationResponse,
)
from app.services.evaluation_registry import EvaluationRegistryService
from app.services.evaluation_service import EvaluationFoundationService

router = APIRouter(tags=["Evaluations"])


# =============================================================================
# Model Registry Endpoints
# =============================================================================


@router.post(
    "/evaluation-models",
    response_model=EvaluationModelResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create category evaluation model in draft status",
)
def create_evaluation_model(
    payload: EvaluationModelCreateRequest,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[
        AuthenticatedUser, Depends(require_permissions(Permission.EVALUATION_MANAGE))
    ],
) -> EvaluationModelResponse:
    """Create a new evaluation model for a product category."""
    registry = EvaluationRegistryService(db)
    user_uuid = uuid.UUID(current_user.id) if current_user.id else None
    try:
        model = registry.create_model(
            category_id=payload.category_id,
            name=payload.name,
            description=payload.description,
            created_by=user_uuid,
        )
    except ValueError as err:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(err))

    return EvaluationModelResponse.model_validate(model)


@router.get(
    "/evaluation-models",
    response_model=EvaluationModelListResponse,
    status_code=status.HTTP_200_OK,
    summary="List evaluation models",
)
def list_evaluation_models(
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[
        AuthenticatedUser, Depends(require_permissions(Permission.EVALUATION_READ))
    ],
    category_id: Annotated[uuid.UUID | None, Query()] = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
) -> EvaluationModelListResponse:
    """Retrieve evaluation models matching query filters."""
    stmt = select(EvaluationModel).options(selectinload(EvaluationModel.versions))
    if category_id:
        stmt = stmt.where(EvaluationModel.category_id == category_id)
    stmt = stmt.limit(limit)

    items = db.execute(stmt).scalars().all()
    return EvaluationModelListResponse(
        total=len(items),
        items=[EvaluationModelResponse.model_validate(m) for m in items],
    )


@router.get(
    "/evaluation-models/{model_id}",
    response_model=EvaluationModelResponse,
    status_code=status.HTTP_200_OK,
    summary="Get evaluation model details",
)
def get_evaluation_model(
    model_id: uuid.UUID,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[
        AuthenticatedUser, Depends(require_permissions(Permission.EVALUATION_READ))
    ],
) -> EvaluationModelResponse:
    """Retrieve evaluation model definition and its registered versions."""
    model = (
        db.execute(
            select(EvaluationModel)
            .where(EvaluationModel.id == model_id)
            .options(selectinload(EvaluationModel.versions))
        )
        .scalars()
        .first()
    )
    if not model:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Evaluation model '{model_id}' not found.",
        )
    return EvaluationModelResponse.model_validate(model)


@router.post(
    "/evaluation-models/{model_id}/versions",
    response_model=EvaluationModelVersionResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Add version definition to evaluation model",
)
def add_model_version(
    model_id: uuid.UUID,
    payload: EvaluationModelVersionCreateRequest,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[
        AuthenticatedUser, Depends(require_permissions(Permission.EVALUATION_MANAGE))
    ],
) -> EvaluationModelVersionResponse:
    """Add a new version configuration to an existing model."""
    registry = EvaluationRegistryService(db)
    user_uuid = uuid.UUID(current_user.id) if current_user.id else None
    try:
        ver = registry.add_version(
            model_id=model_id,
            version=payload.version,
            definition=payload.definition,
            user_id=user_uuid,
        )
    except ValueError as err:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(err))

    return EvaluationModelVersionResponse.model_validate(ver)


@router.post(
    "/evaluation-models/{model_id}/versions/{version_id}/validate",
    response_model=dict[str, Any],
    status_code=status.HTTP_200_OK,
    summary="Validate model version definition",
)
def validate_model_version(
    model_id: uuid.UUID,
    version_id: uuid.UUID,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[
        AuthenticatedUser, Depends(require_permissions(Permission.EVALUATION_MANAGE))
    ],
) -> dict[str, Any]:
    """Validate a draft model version against strict scoring rules and schemas."""
    registry = EvaluationRegistryService(db)
    try:
        validated_cfg = registry.validate_version(version_id)
    except ValueError as err:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(err))

    ver = registry.db.get(EvaluationModelVersion, version_id)
    if not ver:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Evaluation model version '{version_id}' not found",
        )

    return {
        "status": "validated",
        "configuration_hash": str(ver.configuration_hash),
        "parameter_count": len(validated_cfg.parameters),
    }


@router.post(
    "/evaluation-models/{model_id}/versions/{version_id}/publish",
    response_model=EvaluationModelVersionResponse,
    status_code=status.HTTP_200_OK,
    summary="Publish evaluation model version",
)
def publish_model_version(
    model_id: uuid.UUID,
    version_id: uuid.UUID,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[
        AuthenticatedUser, Depends(require_permissions(Permission.EVALUATION_MANAGE))
    ],
) -> EvaluationModelVersionResponse:
    """Publish a validated model version, freezing it as immutable and activating it for the category."""
    registry = EvaluationRegistryService(db)
    user_uuid = uuid.UUID(current_user.id) if current_user.id else None
    try:
        pub_ver = registry.publish_version(version_id, published_by=user_uuid)
    except ValueError as err:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(err))

    return EvaluationModelVersionResponse.model_validate(pub_ver)


@router.post(
    "/evaluation-models/{model_id}/versions/{version_id}/deprecate",
    response_model=EvaluationModelVersionResponse,
    status_code=status.HTTP_200_OK,
    summary="Deprecate published evaluation model version",
)
def deprecate_model_version(
    model_id: uuid.UUID,
    version_id: uuid.UUID,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[
        AuthenticatedUser, Depends(require_permissions(Permission.EVALUATION_MANAGE))
    ],
) -> EvaluationModelVersionResponse:
    """Deprecate a published model version without deleting historical evaluations."""
    registry = EvaluationRegistryService(db)
    user_uuid = uuid.UUID(current_user.id) if current_user.id else None
    try:
        dep_ver = registry.deprecate_version(version_id, user_id=user_uuid)
    except ValueError as err:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(err))

    return EvaluationModelVersionResponse.model_validate(dep_ver)


# =============================================================================
# Evaluation Execution & History Endpoints
# =============================================================================


@router.post(
    "/variants/{variant_id}/evaluations",
    response_model=EvaluationResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Evaluate canonical variant using deterministic engine foundation",
)
def evaluate_variant(
    variant_id: uuid.UUID,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[
        AuthenticatedUser, Depends(require_permissions(Permission.EVALUATION_MANAGE))
    ],
    model_version_id: Annotated[uuid.UUID | None, Query()] = None,
) -> EvaluationResponse:
    """Trigger deterministic evaluation for a variant."""
    service = EvaluationFoundationService(db)
    try:
        evaluation = service.evaluate_variant(
            variant_id=variant_id,
            force_model_version_id=model_version_id,
        )
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


@router.get(
    "/variants/{variant_id}/evaluations",
    response_model=EvaluationListResponse,
    status_code=status.HTTP_200_OK,
    summary="List chronological evaluation history for a canonical variant",
)
@router.get(
    "/variants/{variant_id}/evaluations/history",
    response_model=EvaluationListResponse,
    status_code=status.HTTP_200_OK,
    summary="List chronological evaluation history for a canonical variant (alias)",
)
def list_variant_evaluations(
    variant_id: uuid.UUID,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[
        AuthenticatedUser, Depends(require_permissions(Permission.EVALUATION_READ))
    ],
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
) -> EvaluationListResponse:
    """Retrieve full append-only evaluation history for a variant."""
    items = (
        db.execute(
            select(Evaluation)
            .where(Evaluation.variant_id == variant_id)
            .order_by(Evaluation.created_at.desc())
            .options(selectinload(Evaluation.parameter_results))
            .limit(limit)
        )
        .scalars()
        .all()
    )
    return EvaluationListResponse(
        total=len(items),
        items=[EvaluationResponse.model_validate(e) for e in items],
    )


@router.get(
    "/evaluations/{evaluation_id}",
    response_model=EvaluationResponse,
    status_code=status.HTTP_200_OK,
    summary="Get evaluation outcome by evaluation ID",
)
def get_evaluation_by_id(
    evaluation_id: uuid.UUID,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[
        AuthenticatedUser, Depends(require_permissions(Permission.EVALUATION_READ))
    ],
) -> EvaluationResponse:
    """Retrieve a specific historical evaluation by its primary key."""
    evaluation = (
        db.execute(
            select(Evaluation)
            .where(Evaluation.id == evaluation_id)
            .options(selectinload(Evaluation.parameter_results))
        )
        .scalars()
        .first()
    )
    if not evaluation:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Evaluation '{evaluation_id}' not found.",
        )
    return EvaluationResponse.model_validate(evaluation)


@router.post(
    "/evaluations/{evaluation_id}/recalculate",
    response_model=EvaluationResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Recalculate evaluation (strictly appends a new evaluation record)",
)
def recalculate_evaluation(
    evaluation_id: uuid.UUID,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[
        AuthenticatedUser, Depends(require_permissions(Permission.EVALUATION_MANAGE))
    ],
) -> EvaluationResponse:
    """Re-evaluate variant without modifying the historical evaluation."""
    old_eval = db.get(Evaluation, evaluation_id)
    if not old_eval:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Evaluation '{evaluation_id}' not found.",
        )

    service = EvaluationFoundationService(db)
    new_eval = service.evaluate_variant(
        variant_id=old_eval.variant_id,
        force_model_version_id=old_eval.model_version_id,
    )
    return EvaluationResponse.model_validate(new_eval)


@router.post(
    "/variants/{variant_id}/evaluations/recalculate",
    response_model=EvaluationResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Recalculate variant evaluation (strictly appends a new evaluation record)",
)
def recalculate_variant_evaluation(
    variant_id: uuid.UUID,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[
        AuthenticatedUser, Depends(require_permissions(Permission.EVALUATION_MANAGE))
    ],
    model_version_id: Annotated[uuid.UUID | None, Query()] = None,
) -> EvaluationResponse:
    """Trigger deterministic evaluation for a variant, appending a new historical record."""
    service = EvaluationFoundationService(db)
    try:
        evaluation = service.evaluate_variant(
            variant_id=variant_id,
            force_model_version_id=model_version_id,
        )
    except ValueError as err:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(err),
        )

    return EvaluationResponse.model_validate(evaluation)
