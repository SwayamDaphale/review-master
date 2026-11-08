"""Administrative API endpoints guarded by RBAC permissions."""

import uuid
from datetime import timedelta
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.core.auth import AuthenticatedUser, require_permissions
from app.core.permissions import Permission
from app.core.security import generate_refresh_token, hash_api_key
from app.db.base import utc_now
from app.db.dependencies import get_db
from app.models.operation import ImportToken
from app.repositories.operations_repository import OperationsRepository

router = APIRouter(prefix="/admin", tags=["Administration"])


class AuditLogResponse(BaseModel):
    """Audit log entry response."""

    id: uuid.UUID
    actor_type: str
    actor_id: str | None = None
    action: str
    target_type: str
    target_id: str | None = None
    status: str
    created_at: str


class ProvisionApiKeyRequest(BaseModel):
    """Request payload to provision an API consumer key."""

    name: str = Field(min_length=3, max_length=128, description="Consumer identity or application name")
    expires_in_days: int = Field(default=30, ge=1, le=365, description="Key lifespan in days")


class ProvisionApiKeyResponse(BaseModel):
    """Response returning provisioned API key (displayed once)."""

    api_key: str
    name: str
    expires_at: str


@router.get(
    "/audit-logs",
    response_model=list[AuditLogResponse],
    status_code=status.HTTP_200_OK,
    summary="List operational audit logs",
    description="Inspect audit trail. Strictly restricted to administrative principals with audit:read permission.",
)
def list_audit_logs(
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[
        AuthenticatedUser, Depends(require_permissions(Permission.AUDIT_READ))
    ],
    action: Annotated[str | None, Query(description="Filter by action name")] = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> list[AuditLogResponse]:
    """Retrieve system audit logs."""
    logs = OperationsRepository.list_audit_logs(db, action=action, limit=limit, offset=offset)

    # Log admin action
    OperationsRepository.create_audit_log(
        db,
        actor_type="user",
        actor_id=current_user.id,
        action="admin.audit_logs_read",
        target_type="audit_log",
        status="success",
    )
    db.commit()

    return [
        AuditLogResponse(
            id=log.id,
            actor_type=log.actor_type,
            actor_id=log.actor_id,
            action=log.action,
            target_type=log.target_type,
            target_id=log.target_id,
            status=log.status,
            created_at=log.created_at.isoformat(),
        )
        for log in logs
    ]


@router.post(
    "/api-keys",
    response_model=ProvisionApiKeyResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Provision a new API key for programmatic consumers",
    description="Generates an opaque API key and stores its cryptographic digest. Strictly restricted to admins.",
)
def provision_api_key(
    payload: ProvisionApiKeyRequest,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[
        AuthenticatedUser, Depends(require_permissions(Permission.ROLES_MANAGE))
    ],
) -> ProvisionApiKeyResponse:
    """Provision a new API consumer key."""
    raw_key, _ = generate_refresh_token()
    prefixed_key = f"rm_live_{raw_key}"
    key_hash = hash_api_key(prefixed_key)
    expires = utc_now() + timedelta(days=payload.expires_in_days)

    token = ImportToken(
        token_hash=key_hash,
        user_id=uuid.UUID(current_user.id) if current_user.id != "anonymous" else None,
        context="api_consumer",
        expires_at=expires,
        is_revoked=False,
    )
    db.add(token)

    OperationsRepository.create_audit_log(
        db,
        actor_type="user",
        actor_id=current_user.id,
        action="admin.api_key_provisioned",
        target_type="import_token",
        target_id=str(token.id),
        status="success",
        metadata_payload={"consumer_name": payload.name},
    )
    db.commit()

    return ProvisionApiKeyResponse(
        api_key=prefixed_key,
        name=payload.name,
        expires_at=expires.isoformat(),
    )


@router.delete(
    "/api-keys/{key_hash}",
    status_code=status.HTTP_200_OK,
    summary="Revoke an API consumer key",
    description="Revokes an API consumer key by hash.",
)
def revoke_api_key(
    key_hash: str,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[
        AuthenticatedUser, Depends(require_permissions(Permission.ROLES_MANAGE))
    ],
) -> dict[str, str]:
    """Revoke an API key."""
    revoked = OperationsRepository.revoke_import_token(db, key_hash)
    if not revoked:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="API key not found.",
        )

    OperationsRepository.create_audit_log(
        db,
        actor_type="user",
        actor_id=current_user.id,
        action="admin.api_key_revoked",
        target_type="import_token",
        target_id=key_hash,
        status="success",
    )
    db.commit()
    return {"status": "success", "message": "API key revoked successfully"}

