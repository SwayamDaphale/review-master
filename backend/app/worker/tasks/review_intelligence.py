"""Background tasks for review intelligence, sentiment analysis, and aspect extraction."""

import asyncio
import logging
import uuid
from typing import Any

from celery import Celery, Task  # type: ignore[import-untyped]

import app.worker.celery_app as ca
from app.services.review_intelligence import ReviewIntelligenceService
from app.worker.services.job_service import DurableJobService

logger = logging.getLogger("review_master.tasks.reviews")


def register_review_tasks(celery_app: Celery) -> None:
    """Register review intelligence analysis tasks."""

    @celery_app.task(
        bind=True,
        name="review_master.process_review_analysis",
        max_retries=3,
        default_retry_delay=5,
    )
    def process_review_analysis_task(
        self: Task,
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

        db = ca.SessionLocal()
        try:
            job_service = DurableJobService(db)

            # 1. Deduplication / Idempotent duplicate delivery check
            current_status = job_service.get_job_status(job_id)
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

            # 2. Transition status to running with worker lease
            job_service.start_job(job_id, worker_id=getattr(self.request, "hostname", None))
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
                job_service.complete_job(
                    job_id,
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
                    analysis.error_message
                    or "Review analysis failed during LLM execution."
                )
                if self.request.retries < self.max_retries:
                    countdown = int(
                        DurableJobService.calculate_backoff(self.request.retries + 1)
                    )
                    job_service.fail_job(job_id, error_message=err, can_retry=True)
                    db.commit()
                    raise self.retry(
                        exc=RuntimeError(err),
                        countdown=countdown,
                    )
                else:
                    job_service.fail_job(job_id, error_message=err, can_retry=False)
                    db.commit()
                    return {"job_id": job_id_str, "status": "failed", "error": err}

        except Exception as exc:
            from celery.exceptions import Retry  # type: ignore[import-untyped]

            if isinstance(exc, Retry):
                raise
            logger.error(
                "Unhandled exception processing review analysis job %s: %s",
                job_id,
                exc,
            )
            if self.request.retries < self.max_retries:
                countdown = int(
                    DurableJobService.calculate_backoff(self.request.retries + 1)
                )
                job_service.fail_job(job_id, error_message=str(exc), can_retry=True)
                db.commit()
                raise self.retry(exc=exc, countdown=countdown) from exc
            else:
                job_service.fail_job(job_id, error_message=str(exc), can_retry=False)
                db.commit()
                raise
        finally:
            db.close()
