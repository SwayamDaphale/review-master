"""Review intelligence endpoints for customer feedback analysis, aspects, and summaries."""

import hashlib
import logging
import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.core.auth import AuthenticatedUser, get_current_user, require_permissions
from app.core.permissions import Permission
from app.db.dependencies import get_db
from app.repositories.review_repository import ReviewRepository
from app.schemas.review_intelligence import (
    AnalyzeReviewJobResponse,
    AnalyzeReviewRequest,
    JobStatusResponse,
    ReviewSummaryResponse,
)
from app.services.async_jobs import AsyncJobManager
from app.services.review_intelligence import ReviewIntelligenceService

logger = logging.getLogger("review_master.reviews_api")
router = APIRouter(prefix="/reviews", tags=["Review Intelligence"])


@router.post(
    "/analyze",
    response_model=AnalyzeReviewJobResponse,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Submit review for asynchronous analysis",
    description="Enqueue a customer review for background analysis via Celery worker.",
)
def analyze_review_endpoint(
    payload: AnalyzeReviewRequest,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[
        AuthenticatedUser, Depends(require_permissions(Permission.INGESTION_SUBMIT))
    ],
) -> AnalyzeReviewJobResponse:
    """Submit review text for asynchronous background processing."""
    # 1. Compute deterministic idempotency key
    key = (
        payload.idempotency_key
        or hashlib.sha256(
            f"{payload.product_id}:{payload.variant_id}:{payload.review_source_id}:{payload.review_text}".encode()
        ).hexdigest()
    )

    # 2. Atomically create or retrieve job
    manager = AsyncJobManager(db)
    job, was_created = manager.create_or_get_job(
        idempotency_key=key,
        job_type="review_analysis",
        payload={
            "product_id": str(payload.product_id) if payload.product_id else None,
            "variant_id": str(payload.variant_id) if payload.variant_id else None,
            "source_evidence_id": (
                str(payload.source_evidence_id) if payload.source_evidence_id else None
            ),
            "review_source_id": payload.review_source_id,
        },
        user_id=current_user.id,
    )
    db.commit()

    # 3. If new job, dispatch to background Celery queue
    if was_created and job.status == "pending":
        try:
            from app.worker.celery_app import process_review_analysis_task

            process_review_analysis_task.delay(
                job_id_str=str(job.id),
                review_text=payload.review_text,
                product_id_str=str(payload.product_id) if payload.product_id else None,
                variant_id_str=str(payload.variant_id) if payload.variant_id else None,
                source_evidence_id_str=(
                    str(payload.source_evidence_id)
                    if payload.source_evidence_id
                    else None
                ),
                review_source_id=payload.review_source_id,
            )
        except Exception as e:  # noqa: BLE001 - Non-blocking broker dispatch warning
            logger.warning("Celery broker dispatch failed: %s", e)

    return AnalyzeReviewJobResponse(
        job_id=job.id,
        job_type=job.job_type,
        status=job.status,
        idempotency_key=job.idempotency_key,
        created_at=job.created_at.isoformat() if job.created_at else None,
    )


@router.get(
    "/products/{product_id}/summary",
    response_model=ReviewSummaryResponse,
    summary="Get product review summary",
    description="Retrieve aggregated review summary, aspect breakdowns, and pros/cons for a product.",
)
def get_product_review_summary(
    product_id: uuid.UUID,
    db: Annotated[Session, Depends(get_db)],
    variant_id: Annotated[
        uuid.UUID | None, Query(description="Optional variant scope")
    ] = None,
) -> ReviewSummaryResponse:
    """Retrieve the latest synthesized review summary."""
    summary = ReviewRepository.get_latest_summary(
        db, product_id=product_id, variant_id=variant_id
    )
    if not summary:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No review summary available for this product.",
        )

    return ReviewSummaryResponse(
        id=summary.id,
        product_id=summary.product_id,
        variant_id=summary.variant_id,
        summary_text=summary.summary_text,
        total_reviews_analyzed=summary.total_reviews_analyzed,
        sentiment_distribution=summary.sentiment_distribution,
        aspect_summaries=summary.aspect_summaries,
        key_pros=summary.key_pros,
        key_cons=summary.key_cons,
        confidence=summary.confidence,
        provider=summary.provider,
        model=summary.model,
        version=summary.version,
        created_at=summary.created_at.isoformat() if summary.created_at else "",
    )


@router.post(
    "/products/{product_id}/summarize",
    response_model=ReviewSummaryResponse,
    summary="Synthesize product reviews",
    description="Trigger synthesis of product review summary from analyzed reviews. Requires expert permissions.",
)
async def synthesize_product_reviews(
    product_id: uuid.UUID,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[
        AuthenticatedUser, Depends(require_permissions(Permission.EVALUATION_MANAGE))
    ],
    variant_id: Annotated[
        uuid.UUID | None, Query(description="Optional variant scope")
    ] = None,
) -> ReviewSummaryResponse:
    """Trigger aggregation and synthesis of customer review claims."""
    service = ReviewIntelligenceService(db)
    summary = await service.summarize_product_reviews(
        product_id=product_id, variant_id=variant_id
    )
    if not summary:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot synthesize summary: no completed review analyses found for this product.",
        )
    db.commit()

    return ReviewSummaryResponse(
        id=summary.id,
        product_id=summary.product_id,
        variant_id=summary.variant_id,
        summary_text=summary.summary_text,
        total_reviews_analyzed=summary.total_reviews_analyzed,
        sentiment_distribution=summary.sentiment_distribution,
        aspect_summaries=summary.aspect_summaries,
        key_pros=summary.key_pros,
        key_cons=summary.key_cons,
        confidence=summary.confidence,
        provider=summary.provider,
        model=summary.model,
        version=summary.version,
        created_at=summary.created_at.isoformat() if summary.created_at else "",
    )


@router.get(
    "/jobs/{job_id}",
    response_model=JobStatusResponse,
    summary="Get async review job status",
    description="Check status of an asynchronous review processing job. Restricted to job owner or admins.",
)
def get_job_status(
    job_id: uuid.UUID,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[AuthenticatedUser, Depends(get_current_user)],
) -> JobStatusResponse:
    """Check asynchronous review job status."""
    manager = AsyncJobManager(db)
    job_info = manager.get_job_status(job_id)
    if not job_info:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Job not found."
        )

    # Authorization check: Owner or privileged admin
    job_user_id = job_info.get("user_id")
    is_owner = (job_user_id is not None) and (str(current_user.id) == str(job_user_id))
    is_admin = (
        "admin" in current_user.roles
        or current_user.has_permission(Permission.USERS_MANAGE)
        or current_user.has_permission(Permission.INGESTION_READ)
    )

    if not (is_owner or is_admin):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access forbidden: you do not have permission to view this job.",
        )

    return JobStatusResponse(
        job_id=uuid.UUID(str(job_info["job_id"])),
        job_type=job_info.get("job_type", "review_analysis"),
        status=job_info.get("status", "pending"),
        created_at=str(job_info["created_at"]) if job_info.get("created_at") else None,
        completed_at=str(job_info["completed_at"])
        if job_info.get("completed_at")
        else None,
        error_summary=job_info.get("error_summary"),
        result_summary=job_info.get("result_summary"),
    )
