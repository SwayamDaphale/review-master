"""API endpoints for listing ingestion, job tracking, and evidence retrieval."""

import json
import logging
import uuid
from typing import Annotated

from fastapi import (
    APIRouter,
    Depends,
    Header,
    HTTPException,
    Request,
    Response,
    status,
)
from sqlalchemy.orm import Session

from app.contracts.extraction.base import (
    ContractValidationError,
    UnsupportedContractError,
    UnsupportedVersionError,
)
from app.core.auth import AuthenticatedUser, get_current_user, require_permissions
from app.core.permissions import Permission
from app.core.rate_limit import ingest_limiter
from app.db.dependencies import get_db
from app.models.extraction import IngestionJob
from app.schemas.ingestion import (
    IngestionJobStatusResponse,
    ListingIngestResponse,
)
from app.services.async_jobs import AsyncJobManager
from app.services.evidence_storage import (
    EvidenceNotFoundError,
    EvidenceStorageService,
    IntegrityMismatchError,
    StorageUnavailableError,
)
from app.services.ingestion_service import IngestionService

logger = logging.getLogger("review_master.api.ingestion")

router = APIRouter(tags=["Listing Ingestion"])
MAX_PAYLOAD_BYTES = 2 * 1024 * 1024  # 2 Megabytes


@router.post(
    "/listings/ingest",
    response_model=ListingIngestResponse,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Ingest marketplace product listing extraction",
    description="Accepts legacy frozen smartphone or generalized extraction snapshots, validates, persists evidence, and schedules background processing.",
    dependencies=[Depends(ingest_limiter)],
)
async def ingest_listing_endpoint(
    request: Request,
    response: Response,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[
        AuthenticatedUser, Depends(require_permissions(Permission.INGESTION_SUBMIT))
    ],
    idempotency_key: Annotated[
        str | None,
        Header(
            alias="Idempotency-Key",
            description="Optional client idempotency key to prevent duplicate processing",
        ),
    ] = None,
) -> ListingIngestResponse:
    """Accept and durably enqueue an extraction snapshot for background processing."""
    # 1. Payload size guard
    content_length = request.headers.get("content-length")
    if content_length and int(content_length) > MAX_PAYLOAD_BYTES:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f"Extraction payload exceeds maximum allowed size of {MAX_PAYLOAD_BYTES} bytes.",
        )

    # 2. Capture raw request bytes
    raw_bytes = await request.body()
    if not raw_bytes or len(raw_bytes) > MAX_PAYLOAD_BYTES:
        if len(raw_bytes) > MAX_PAYLOAD_BYTES:
            raise HTTPException(
                status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                detail=f"Extraction payload exceeds maximum allowed size of {MAX_PAYLOAD_BYTES} bytes.",
            )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Request body cannot be empty.",
        )

    # 3. Parse JSON safely
    try:
        payload_dict = json.loads(raw_bytes.decode("utf-8"))
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Malformed JSON payload: {e}",
        ) from e

    # 4. Service execution
    ingestion_service = IngestionService(db)
    try:
        job, rec, contract_name, schema_version, is_duplicate = (
            ingestion_service.create_durable_ingestion(
                raw_bytes=raw_bytes,
                payload_dict=payload_dict,
                user_id=current_user.id,
                idempotency_key_header=idempotency_key,
            )
        )
    except (UnsupportedContractError, UnsupportedVersionError) as err:
        logger.warning("Unsupported contract or version: %s", err)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(err),
        ) from err
    except ContractValidationError as err:
        logger.warning("Extraction contract validation failed: %s", err.errors)
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={"error_type": "contract_validation_error", "detail": err.errors},
        ) from err
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Unhandled ingestion error: %s", e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to accept extraction snapshot.",
        ) from e

    # 5. Handle duplicate replay vs newly accepted
    if is_duplicate:
        response.status_code = status.HTTP_200_OK
    else:
        response.status_code = status.HTTP_202_ACCEPTED
        # Enqueue background Celery task
        try:
            from app.worker.celery_app import process_listing_ingestion_task

            process_listing_ingestion_task.delay(job_id_str=str(job.id))
        except Exception as e:  # noqa: BLE001
            logger.warning("Celery dispatch non-blocking notice: %s", e)

    ingestion_id = (rec.record_id if rec else job.record_id) or str(job.id)

    return ListingIngestResponse(
        ingestion_id=ingestion_id,
        job_id=job.id,
        status=job.status,
        contract_type=contract_name,
        schema_version=schema_version,
        duplicate=is_duplicate,
        created_at=job.created_at.isoformat() if job.created_at else "",
    )


@router.get(
    "/ingestion-jobs/{job_id}",
    response_model=IngestionJobStatusResponse,
    status_code=status.HTTP_200_OK,
    summary="Get ingestion job status",
    description="Retrieve sanitized background status and outcome of an extraction ingestion job.",
)
def get_ingestion_job_status(
    job_id: uuid.UUID,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[AuthenticatedUser, Depends(get_current_user)],
) -> IngestionJobStatusResponse:
    """Fetch sanitized status for an ingestion job with ownership enforcement."""
    job = db.get(IngestionJob, job_id)
    if not job or job.job_type != "listing_ingestion":
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Ingestion job '{job_id}' not found.",
        )

    # Ownership / Admin check
    payload = job.payload or {}
    job_user_id = payload.get("user_id")
    is_admin = ("admin" in current_user.roles) or (
        Permission.USERS_MANAGE in current_user.permissions
    )

    if not is_admin and str(job_user_id) != str(current_user.id):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to access this ingestion job.",
        )

    res_summary = payload.get("result")
    completed_at = (
        job.updated_at.isoformat()
        if (job.status in ("completed", "failed") and job.updated_at)
        else None
    )

    return IngestionJobStatusResponse(
        job_id=str(job.id),
        job_type=job.job_type,
        status=job.status,
        user_id=job_user_id,
        contract_type=payload.get("contract_type"),
        schema_version=payload.get("schema_version"),
        created_at=job.created_at.isoformat() if job.created_at else None,
        completed_at=completed_at,
        error_summary=AsyncJobManager.sanitize_error(job.error_message),
        result_summary=res_summary,
    )


@router.get(
    "/ingestion-jobs/{job_id}/evidence",
    status_code=status.HTTP_200_OK,
    summary="Retrieve original preserved evidence for ingestion job",
    description="Download the immutable raw extraction snapshot artifact from SeaweedFS object storage.",
)
def get_ingestion_job_evidence(
    job_id: uuid.UUID,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[AuthenticatedUser, Depends(get_current_user)],
) -> Response:
    """Retrieve original evidence bytes from SeaweedFS with authorization."""
    job = db.get(IngestionJob, job_id)
    if not job or job.job_type != "listing_ingestion":
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Ingestion job '{job_id}' not found.",
        )

    # Ownership check
    payload = job.payload or {}
    job_user_id = payload.get("user_id")
    is_admin = ("admin" in current_user.roles) or (
        Permission.USERS_MANAGE in current_user.permissions
    )

    if not is_admin and str(job_user_id) != str(current_user.id):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to access evidence for this ingestion job.",
        )

    storage_key = payload.get("storage_object_key")
    expected_digest = payload.get("payload_sha256")
    if not storage_key:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No evidence object is associated with this job.",
        )

    storage = EvidenceStorageService()
    try:
        content_bytes, content_type, actual_digest = storage.retrieve_evidence(
            object_key=storage_key,
            expected_sha256=expected_digest,
        )
    except EvidenceNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Evidence artifact not found in object storage.",
        )
    except IntegrityMismatchError as ie:
        logger.error("Evidence integrity error: %s", ie)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Evidence artifact failed cryptographic integrity check.",
        )
    except StorageUnavailableError as se:
        logger.error("Evidence storage error: %s", se)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Object storage service temporarily unavailable.",
        )

    return Response(
        content=content_bytes,
        media_type=content_type,
        headers={
            "ETag": f'"{actual_digest}"',
            "X-Evidence-SHA256": actual_digest,
            "X-Evidence-Object-Key": storage_key,
            "Content-Disposition": f'attachment; filename="evidence-{job.record_id or job.id}.json"',
        },
    )
