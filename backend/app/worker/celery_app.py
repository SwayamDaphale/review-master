"""Celery worker application and background task definitions for review intelligence."""

import asyncio
import logging
import uuid
from typing import Any

from celery import Celery  # type: ignore[import-untyped]

from app.core.config import settings
from app.db.session import SessionLocal
from app.services.async_jobs import AsyncJobManager
from app.services.ingestion_service import IngestionService
from app.services.review_intelligence import ReviewIntelligenceService

logger = logging.getLogger("review_master.worker")

celery_app = Celery(
    "review_master",
    broker=settings.CELERY_BROKER_URL,
    backend=settings.CELERY_RESULT_BACKEND,
)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    task_track_started=True,
    task_acks_late=True,
    worker_prefetch_multiplier=1,
)


@celery_app.task(
    bind=True,
    name="review_master.process_review_analysis",
    max_retries=3,
    default_retry_delay=5,
)
def process_review_analysis_task(
    self,
    job_id_str: str,
    review_text: str,
    product_id_str: str | None = None,
    variant_id_str: str | None = None,
    source_evidence_id_str: str | None = None,
    review_source_id: str | None = None,
) -> dict[str, Any]:
    """Execute background review analysis, persist results, and transition job status."""
    job_id = uuid.UUID(job_id_str)
    product_id = uuid.UUID(product_id_str) if product_id_str else None
    variant_id = uuid.UUID(variant_id_str) if variant_id_str else None
    source_evidence_id = (
        uuid.UUID(source_evidence_id_str) if source_evidence_id_str else None
    )

    db = SessionLocal()
    try:
        job_manager = AsyncJobManager(db)

        # 1. Deduplication / Idempotent duplicate delivery check
        current_status = job_manager.get_job_status(job_id)
        if current_status and current_status.get("status") == "completed":
            logger.info(
                "Job %s is already completed; skipping duplicate task delivery.",
                job_id,
            )
            return {"job_id": job_id_str, "status": "completed"}

        if (
            self.request.retries == 0
            and current_status
            and current_status.get("status") == "running"
        ):
            logger.info(
                "Job %s is already running; skipping duplicate task delivery.",
                job_id,
            )
            return {"job_id": job_id_str, "status": "running"}

        # 2. Transition status to running
        job_manager.update_job_status(job_id, status="running")
        db.commit()

        # 3. Execute review intelligence service in event loop
        service = ReviewIntelligenceService(db)
        analysis = asyncio.run(
            service.analyze_review(
                review_text=review_text,
                product_id=product_id,
                variant_id=variant_id,
                source_evidence_id=source_evidence_id,
                review_source_id=review_source_id,
            )
        )
        db.commit()

        # 4. Check analysis outcome
        if analysis.status == "completed":
            job_manager.update_job_status(
                job_id,
                status="completed",
                result_payload={
                    "analysis_id": str(analysis.id),
                    "status": "completed",
                },
            )
            db.commit()
            return {
                "job_id": job_id_str,
                "status": "completed",
                "analysis_id": str(analysis.id),
            }
        else:
            err = (
                analysis.error_message or "Review analysis failed during LLM execution."
            )
            if self.request.retries < self.max_retries:
                logger.warning(
                    "Job %s failed on attempt %d/%d; scheduling retry in %ds...",
                    job_id,
                    self.request.retries + 1,
                    self.max_retries,
                    2**self.request.retries,
                )
                raise self.retry(
                    exc=RuntimeError(err),
                    countdown=2**self.request.retries,
                )
            else:
                job_manager.update_job_status(
                    job_id, status="failed", error_message=err
                )
                db.commit()
                return {"job_id": job_id_str, "status": "failed", "error": err}

    except Exception as exc:
        # Avoid double-handling Celery MaxRetriesExceededError or Retry
        from celery.exceptions import Retry  # type: ignore[import-untyped]

        if isinstance(exc, Retry):
            raise
        logger.error(
            "Unhandled exception processing review analysis job %s: %s",
            job_id,
            exc,
        )
        if self.request.retries < self.max_retries:
            raise self.retry(exc=exc, countdown=2**self.request.retries) from exc
        else:
            job_manager.update_job_status(
                job_id, status="failed", error_message=str(exc)
            )
            db.commit()
            raise
    finally:
        db.close()


@celery_app.task(
    bind=True,
    name="review_master.process_listing_ingestion",
    max_retries=3,
    default_retry_delay=5,
)
def process_listing_ingestion_task(
    self,
    job_id_str: str,
) -> dict[str, Any]:
    """Execute background listing ingestion, catalog matching, and evidence persistence."""
    job_id = uuid.UUID(job_id_str)
    db = SessionLocal()
    try:
        job_manager = AsyncJobManager(db)

        # 1. Deduplication / Idempotent duplicate delivery check
        current_status = job_manager.get_job_status(job_id)
        if current_status and current_status.get("status") == "completed":
            logger.info(
                "Ingestion job %s is already completed; skipping duplicate task delivery.",
                job_id,
            )
            return {"job_id": job_id_str, "status": "completed"}

        if (
            self.request.retries == 0
            and current_status
            and current_status.get("status") == "running"
        ):
            logger.info(
                "Ingestion job %s is already running; skipping duplicate task delivery.",
                job_id,
            )
            return {"job_id": job_id_str, "status": "running"}

        # 2. Transition status to running
        job_manager.update_job_status(job_id, status="running")
        db.commit()

        # 3. Execute domain ingestion pipeline
        service = IngestionService(db)
        result = service.process_canonical_ingestion(job_id)
        return result

    except Exception as exc:
        from celery.exceptions import Retry  # type: ignore[import-untyped]

        if isinstance(exc, Retry):
            raise
        logger.error(
            "Unhandled exception processing listing ingestion job %s: %s",
            job_id,
            exc,
        )
        if self.request.retries < self.max_retries:
            raise self.retry(exc=exc, countdown=2**self.request.retries) from exc
        else:
            job_manager.update_job_status(
                job_id, status="failed", error_message=str(exc)
            )
            db.commit()
            raise
    finally:
        db.close()

