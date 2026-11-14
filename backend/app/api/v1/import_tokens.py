"""Secure single-use import handoff token REST endpoints (Module 13)."""

import hashlib
import json
import logging
import secrets
import uuid
from datetime import timedelta
from typing import Annotated

from fastapi import APIRouter, Depends, Header, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.auth import AuthenticatedUser, get_current_user
from app.core.rate_limit import import_token_limiter
from app.db.base import utc_now
from app.db.dependencies import get_db
from app.models.extraction import IngestionJob
from app.models.operation import ImportToken
from app.schemas.import_token import (
    ImportTokenConsumeRequest,
    ImportTokenConsumeResponse,
    ImportTokenCreateRequest,
    ImportTokenCreateResponse,
)

logger = logging.getLogger("review_master.api.import_tokens")

router = APIRouter(prefix="/import-tokens", tags=["Import Tokens"])

TOKEN_EXPIRATION_MINUTES = 15


def _hash_token(raw_token: str) -> str:
    """Compute SHA-256 digest of opaque token for constant-time lookup and secure persistence."""
    return hashlib.sha256(raw_token.encode("utf-8")).hexdigest()


def get_optional_user(
    db: Annotated[Session, Depends(get_db)],
    authorization: Annotated[str | None, Header()] = None,
    x_api_key: Annotated[str | None, Header(alias="X-API-Key")] = None,
) -> AuthenticatedUser | None:
    """Resolve current user if credentials are supplied, otherwise return None."""
    if not authorization and not x_api_key:
        return None
    try:
        return get_current_user(authorization=authorization, x_api_key=x_api_key, db=db)
    except HTTPException:
        return None


@router.post(
    "",
    response_model=ImportTokenCreateResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a single-use import handoff token",
    description="Generates a cryptographically random, high-entropy single-use token for transferring browser extension data to the web app. Persists only the SHA-256 digest.",
    dependencies=[Depends(import_token_limiter)],
)
def create_import_token(
    payload: ImportTokenCreateRequest,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[AuthenticatedUser | None, Depends(get_optional_user)] = None,
) -> ImportTokenCreateResponse:
    """Generate high-entropy opaque import token, persisting only its cryptographic hash."""
    # 1. Generate 256-bit cryptographically secure random token (URL-safe)
    raw_token = secrets.token_urlsafe(32)
    token_hash = _hash_token(raw_token)

    # 2. Expiration window (15 minutes)
    now = utc_now()
    expires_at = now + timedelta(minutes=TOKEN_EXPIRATION_MINUTES)

    # 3. Assemble context JSON string within 255 chars
    ctx_dict: dict[str, str] = {}
    if payload.job_id:
        ctx_dict["job_id"] = str(payload.job_id)
    if payload.listing_id:
        ctx_dict["listing_id"] = str(payload.listing_id)
    if payload.context_data:
        for k, v in payload.context_data.items():
            if len(json.dumps(ctx_dict)) < 220:
                ctx_dict[str(k)] = str(v)[:50]

    context_str = json.dumps(ctx_dict) if ctx_dict else None
    user_id = uuid.UUID(current_user.id) if (current_user and current_user.is_authenticated and current_user.id and not current_user.id.startswith("api-")) else None

    # 4. Persist only hash in import_tokens table
    db_token = ImportToken(
        token_hash=token_hash,
        user_id=user_id,
        context=context_str,
        expires_at=expires_at,
        is_revoked=False,
        used_at=None,
    )
    db.add(db_token)
    db.commit()

    logger.info("Import handoff token created (hash prefix: %s...)", token_hash[:8])

    return ImportTokenCreateResponse(
        import_code=raw_token,
        expires_at=expires_at,
    )


@router.post(
    "/consume",
    response_model=ImportTokenConsumeResponse,
    status_code=status.HTTP_200_OK,
    summary="Atomically consume a single-use import handoff token",
    description="Validates token hash, checks expiration, revocation, and atomic single-use status under row locking. Marks as consumed in the same transaction.",
    dependencies=[Depends(import_token_limiter)],
)
def consume_import_token(
    payload: ImportTokenConsumeRequest,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[AuthenticatedUser | None, Depends(get_optional_user)] = None,
) -> ImportTokenConsumeResponse:
    """Atomically consume an import token, preventing replay and concurrent double consumption."""
    raw_token = payload.import_code.strip()
    if not raw_token:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Import code cannot be empty.",
        )

    token_hash = _hash_token(raw_token)
    now = utc_now()

    # 1. Query with row-level exclusive lock (FOR UPDATE) to serialize concurrent consumption attempts
    stmt = (
        select(ImportToken)
        .where(ImportToken.token_hash == token_hash)
        .with_for_update()
    )
    token_record = db.execute(stmt).scalar_one_or_none()

    if not token_record:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Invalid import code. The code does not exist.",
        )

    # 2. Check revocation
    if token_record.is_revoked:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="This import code has been revoked and cannot be used.",
        )

    # 3. Check replay (already consumed)
    if token_record.used_at is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="This import code has already been consumed. Each code is strictly single-use.",
        )

    # 4. Check expiration
    if token_record.expires_at < now:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="This import code has expired. Please initiate a new import from the extension.",
        )

    # 5. Check user binding if bound to a specific user
    if token_record.user_id is not None:
        if not current_user or not current_user.is_authenticated:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Authentication required to consume this user-bound import code.",
            )
        try:
            curr_uuid = uuid.UUID(current_user.id)
            if curr_uuid != token_record.user_id:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="This import code belongs to a different user account.",
                )
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Invalid user context.",
            )

    # 6. Mark atomically as consumed within this transaction
    token_record.used_at = now
    db.commit()

    logger.info("Import handoff token successfully consumed (hash prefix: %s...)", token_hash[:8])

    # 7. Unpack context to retrieve bound job or listing
    job_id_str: str | None = None
    listing_id_str: str | None = None
    job_status: str | None = None
    resolved_payload: dict | None = None

    if token_record.context:
        try:
            ctx = json.loads(token_record.context)
            if isinstance(ctx, dict):
                job_id_str = ctx.get("job_id")
                listing_id_str = ctx.get("listing_id")
        except json.JSONDecodeError:
            logger.debug("Failed to decode token context as JSON")

    if job_id_str:
        try:
            job_uuid = uuid.UUID(job_id_str)
            job = db.get(IngestionJob, job_uuid)
            if job:
                job_status = job.status
                resolved_payload = job.payload
        except (ValueError, TypeError):
            logger.debug("Invalid UUID format for job_id: %s", job_id_str)

    return ImportTokenConsumeResponse(
        status="consumed",
        job_id=job_id_str,
        listing_id=listing_id_str,
        context=token_record.context,
        job_status=job_status,
        payload=resolved_payload,
        consumed_at=now,
    )
