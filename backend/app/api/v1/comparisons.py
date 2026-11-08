"""Comparison sessions API endpoints with object-level ownership authorization."""

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.core.auth import AuthenticatedUser, require_permissions
from app.core.permissions import Permission, RoleName
from app.db.dependencies import get_db
from app.models.comparison import ComparisonSession
from app.repositories.comparison_repository import ComparisonRepository

router = APIRouter(prefix="/comparisons", tags=["Comparisons"])


class CreateComparisonRequest(BaseModel):
    """Payload to create comparison session."""

    title: str | None = Field(default=None, max_length=255)
    category_id: uuid.UUID | None = None


class AddComparisonItemRequest(BaseModel):
    """Payload to add item to comparison session."""

    product_id: uuid.UUID
    variant_id: uuid.UUID | None = None
    position: int = 0


class ComparisonItemResponse(BaseModel):
    """Comparison item representation."""

    id: uuid.UUID
    session_id: uuid.UUID
    product_id: uuid.UUID
    variant_id: uuid.UUID | None = None
    position: int


class ComparisonSessionResponse(BaseModel):
    """Comparison session representation."""

    id: uuid.UUID
    user_id: uuid.UUID | None = None
    title: str | None = None
    category_id: uuid.UUID | None = None
    status: str
    items: list[ComparisonItemResponse] = []


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
    response_model=ComparisonSessionResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a new comparison session",
    description="Creates a persistent comparison session bound to the authenticated user.",
)
def create_session(
    payload: CreateComparisonRequest,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[
        AuthenticatedUser, Depends(require_permissions(Permission.COMPARISON_WRITE))
    ],
) -> ComparisonSessionResponse:
    """Create a new comparison session."""
    user_uuid = None
    try:
        user_uuid = uuid.UUID(current_user.id)
    except ValueError:
        pass

    session = ComparisonRepository.create_session(
        db,
        user_id=user_uuid,
        title=payload.title,
        category_id=payload.category_id,
    )
    db.commit()

    return ComparisonSessionResponse(
        id=session.id,
        user_id=session.user_id,
        title=session.title,
        category_id=session.category_id,
        status=session.status,
        items=[],
    )


@router.get(
    "/{session_id}",
    response_model=ComparisonSessionResponse,
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
) -> ComparisonSessionResponse:
    """Retrieve comparison session ensuring object-level authorization."""
    session = ComparisonRepository.get_session_by_id(db, session_id)
    if not session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Comparison session '{session_id}' not found.",
        )

    _verify_session_ownership(session, current_user)

    items = ComparisonRepository.get_session_items(db, session.id)
    return ComparisonSessionResponse(
        id=session.id,
        user_id=session.user_id,
        title=session.title,
        category_id=session.category_id,
        status=session.status,
        items=[
            ComparisonItemResponse(
                id=item.id,
                session_id=item.session_id,
                product_id=item.product_id,
                variant_id=item.variant_id,
                position=item.position,
            )
            for item in items
        ],
    )


@router.post(
    "/{session_id}/items",
    response_model=ComparisonItemResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Add an item to a comparison session",
    description="Adds product/variant to comparison session. Enforces object-level ownership authorization.",
)
def add_item_to_session(
    session_id: uuid.UUID,
    payload: AddComparisonItemRequest,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[
        AuthenticatedUser, Depends(require_permissions(Permission.COMPARISON_WRITE))
    ],
) -> ComparisonItemResponse:
    """Add item ensuring caller owns the comparison session."""
    session = ComparisonRepository.get_session_by_id(db, session_id)
    if not session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Comparison session '{session_id}' not found.",
        )

    _verify_session_ownership(session, current_user)

    item = ComparisonRepository.add_item(
        db,
        session_id=session.id,
        product_id=payload.product_id,
        variant_id=payload.variant_id,
        position=payload.position,
    )
    db.commit()

    return ComparisonItemResponse(
        id=item.id,
        session_id=item.session_id,
        product_id=item.product_id,
        variant_id=item.variant_id,
        position=item.position,
    )

