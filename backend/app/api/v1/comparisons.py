"""Comparison sessions and matrix API endpoints with strict ownership and concurrency controls."""

import uuid
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.core.auth import AuthenticatedUser, require_permissions
from app.core.permissions import Permission, RoleName
from app.db.dependencies import get_db
from app.models.comparison import ComparisonSession
from app.repositories.comparison_repository import (
    ActiveComparisonSessionLimitError,
    ComparisonValidationError,
)
from app.schemas.comparison import (
    AddComparisonVariantRequest,
    ComparisonItemSchema,
    ComparisonMatrixResponse,
    ComparisonSessionSchema,
    CreateComparisonSessionRequest,
)
from app.services.comparison_service import ComparisonService

router = APIRouter(prefix="/comparisons", tags=["Comparisons"])


def _verify_session_ownership(session: ComparisonSession, current_user: AuthenticatedUser) -> None:
    """Enforce object-level authorization: callers can only access their own private sessions."""
    if session.user_id is not None:
        try:
            user_uuid = uuid.UUID(current_user.id)
            if session.user_id != user_uuid and not current_user.has_role(RoleName.ADMIN):
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Forbidden: Cannot access another user's private comparison session.",
                )
        except ValueError:
            if not current_user.has_role(RoleName.ADMIN):
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Forbidden: Cannot access another user's private comparison session.",
                )


@router.post(
    "",
    response_model=ComparisonSessionSchema,
    status_code=status.HTTP_201_CREATED,
    summary="Create a new comparison session",
    description="Creates a persistent comparison session bound to the authenticated user. Enforces maximum 2 active sessions.",
)
def create_session(
    payload: CreateComparisonSessionRequest,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[
        AuthenticatedUser, Depends(require_permissions(Permission.COMPARISON_WRITE))
    ],
) -> ComparisonSessionSchema:
    """Create a new comparison session."""
    user_uuid = None
    try:
        user_uuid = uuid.UUID(current_user.id)
    except ValueError:
        pass

    service = ComparisonService(db)
    try:
        session = service.create_session(
            user_id=user_uuid,
            title=payload.title,
            category_id=payload.category_id,
        )
        db.commit()
    except ActiveComparisonSessionLimitError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(exc),
        )

    return ComparisonSessionSchema(
        id=session.id,
        user_id=session.user_id,
        anonymous_session_token=session.anonymous_session_token,
        title=session.title,
        status=session.status,
        category_id=session.category_id,
        created_at=session.created_at,
        updated_at=session.updated_at,
        items=[],
    )


@router.get(
    "",
    response_model=list[ComparisonSessionSchema],
    status_code=status.HTTP_200_OK,
    summary="List current user's comparison sessions",
    description="Lists comparison sessions belonging to the caller. Defaults to active sessions.",
)
def list_sessions(
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[
        AuthenticatedUser, Depends(require_permissions(Permission.COMPARISON_READ))
    ],
    status_filter: str | None = Query(default="active", alias="status"),
) -> list[ComparisonSessionSchema]:
    """List caller's sessions."""
    try:
        user_uuid = uuid.UUID(current_user.id)
    except ValueError:
        return []

    service = ComparisonService(db)
    status_arg = None if status_filter == "all" else status_filter
    sessions = service.list_user_sessions(user_uuid, status=status_arg)

    return [
        ComparisonSessionSchema(
            id=s.id,
            user_id=s.user_id,
            anonymous_session_token=s.anonymous_session_token,
            title=s.title,
            status=s.status,
            category_id=s.category_id,
            created_at=s.created_at,
            updated_at=s.updated_at,
            items=[
                ComparisonItemSchema(
                    id=i.id,
                    session_id=i.session_id,
                    product_id=i.product_id,
                    variant_id=i.variant_id,
                    position=i.position,
                    created_at=i.created_at,
                    product_name=i.product.name if i.product else None,
                    sku_label=i.variant.sku_label if i.variant else None,
                )
                for i in s.items
            ],
        )
        for s in sessions
    ]


@router.get(
    "/{session_id}",
    response_model=ComparisonSessionSchema,
    status_code=status.HTTP_200_OK,
    summary="Get comparison session with items",
    description="Retrieves a comparison session. Enforces object-level ownership authorization.",
)
def get_session(
    session_id: uuid.UUID,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[
        AuthenticatedUser, Depends(require_permissions(Permission.COMPARISON_READ))
    ],
) -> ComparisonSessionSchema:
    """Retrieve comparison session ensuring object-level authorization."""
    service = ComparisonService(db)
    session = service.get_session(session_id)
    if not session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Comparison session '{session_id}' not found.",
        )

    _verify_session_ownership(session, current_user)

    return ComparisonSessionSchema(
        id=session.id,
        user_id=session.user_id,
        anonymous_session_token=session.anonymous_session_token,
        title=session.title,
        status=session.status,
        category_id=session.category_id,
        created_at=session.created_at,
        updated_at=session.updated_at,
        items=[
            ComparisonItemSchema(
                id=item.id,
                session_id=item.session_id,
                product_id=item.product_id,
                variant_id=item.variant_id,
                position=item.position,
                created_at=item.created_at,
                product_name=item.product.name if item.product else None,
                sku_label=item.variant.sku_label if item.variant else None,
            )
            for item in session.items
        ],
    )


@router.post(
    "/{session_id}/archive",
    response_model=ComparisonSessionSchema,
    status_code=status.HTTP_200_OK,
    summary="Archive a comparison session",
    description="Archives a comparison session, releasing an active session slot.",
)
def archive_session(
    session_id: uuid.UUID,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[
        AuthenticatedUser, Depends(require_permissions(Permission.COMPARISON_WRITE))
    ],
) -> ComparisonSessionSchema:
    """Archive comparison session."""
    service = ComparisonService(db)
    session = service.get_session(session_id)
    if not session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Comparison session '{session_id}' not found.",
        )

    _verify_session_ownership(session, current_user)

    archived = service.archive_session(session_id)
    return ComparisonSessionSchema(
        id=archived.id,
        user_id=archived.user_id,
        anonymous_session_token=archived.anonymous_session_token,
        title=archived.title,
        status=archived.status,
        category_id=archived.category_id,
        created_at=archived.created_at,
        updated_at=archived.updated_at,
        items=[],
    )


@router.post(
    "/{session_id}/items",
    response_model=ComparisonItemSchema,
    status_code=status.HTTP_201_CREATED,
    summary="Add a variant to a comparison session",
    description="Adds a variant ensuring same category and maximum 5 items capacity.",
)
def add_item_to_session(
    session_id: uuid.UUID,
    payload: AddComparisonVariantRequest,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[
        AuthenticatedUser, Depends(require_permissions(Permission.COMPARISON_WRITE))
    ],
) -> ComparisonItemSchema:
    """Add variant ensuring caller owns the comparison session."""
    service = ComparisonService(db)
    session = service.get_session(session_id)
    if not session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Comparison session '{session_id}' not found.",
        )

    _verify_session_ownership(session, current_user)

    try:
        return service.add_variant_to_session(
            session_id=session.id,
            variant_id=payload.variant_id,
            position=payload.position,
        )
    except ComparisonValidationError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        )


@router.delete(
    "/{session_id}/items/{variant_id}",
    status_code=status.HTTP_200_OK,
    summary="Remove a variant from comparison session",
    description="Removes a variant from the active comparison session.",
)
def remove_item_from_session(
    session_id: uuid.UUID,
    variant_id: uuid.UUID,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[
        AuthenticatedUser, Depends(require_permissions(Permission.COMPARISON_WRITE))
    ],
) -> dict[str, Any]:
    """Remove variant from session."""
    service = ComparisonService(db)
    session = service.get_session(session_id)
    if not session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Comparison session '{session_id}' not found.",
        )

    _verify_session_ownership(session, current_user)

    try:
        removed = service.remove_variant_from_session(session_id, variant_id)
        if not removed:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Variant '{variant_id}' not found in comparison session.",
            )
        return {"status": "success", "message": f"Variant '{variant_id}' removed from comparison session."}
    except ComparisonValidationError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        )


@router.get(
    "/{session_id}/matrix",
    response_model=ComparisonMatrixResponse,
    status_code=status.HTTP_200_OK,
    summary="Get category-aware comparison matrix",
    description="Builds the full side-by-side comparison matrix with strictly separated evaluation, price, specs, and community dimensions.",
)
def get_comparison_matrix(
    session_id: uuid.UUID,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[
        AuthenticatedUser, Depends(require_permissions(Permission.COMPARISON_READ))
    ],
    recalculate: bool = Query(default=False, description="Explicitly trigger fresh evaluation calculations"),
) -> ComparisonMatrixResponse:
    """Retrieve full comparison matrix for session."""
    service = ComparisonService(db)
    session = service.get_session(session_id)
    if not session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Comparison session '{session_id}' not found.",
        )

    _verify_session_ownership(session, current_user)

    return service.get_comparison_matrix(session_id, force_recalculate=recalculate)
