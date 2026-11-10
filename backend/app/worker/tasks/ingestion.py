"""Background tasks for evidence ingestion and canonical catalog creation."""

import logging
import uuid
from typing import Any

from celery import Celery, Task  # type: ignore[import-untyped]

import app.worker.celery_app as ca
from app.services.ingestion_service import IngestionService
from app.worker.services.job_service import DurableJobService

logger = logging.getLogger("review_master.tasks.ingestion")


def register_ingestion_tasks(celery_app: Celery) -> None:
    """Register listing ingestion tasks on Celery app."""

    @celery_app.task(
        bind=True,
        name="ingestion.process",
        max_retries=3,
        default_retry_delay=5,
    )
    def process_ingestion_canonical(self: Task, job_id_str: str) -> dict[str, Any]:
        """Execute background listing ingestion, catalog matching, and evidence persistence."""
        job_id = uuid.UUID(job_id_str)
        db = ca.SessionLocal()
        try:
            job_service = DurableJobService(db)
            worker_id = getattr(self.request, "hostname", "worker")

            # 1. Deduplication / Idempotent delivery check
            status = job_service.get_job_status(job_id)
            if status and status.get("status") == "completed":
                logger.info(
                    "Ingestion job %s already completed; skipping duplicate execution.",
                    job_id,
                )
                return {"job_id": job_id_str, "status": "completed"}

            if self.request.retries == 0 and status and status.get("status") == "running":
                logger.info(
                    "Ingestion job %s is already running; skipping duplicate execution.",
                    job_id,
                )
                return {"job_id": job_id_str, "status": "running"}

            # 2. Transition status to running with worker lease
            job_service.start_job(job_id, worker_id=worker_id)
            db.commit()

            # 3. Execute canonical ingestion pipeline
            service = IngestionService(db)
            result = service.process_canonical_ingestion(job_id)
            job_service.complete_job(job_id, result_payload=result)
            db.commit()
            return result

        except Exception as exc:
            from celery.exceptions import Retry  # type: ignore[import-untyped]

            if isinstance(exc, Retry):
                raise
            logger.error("Error processing ingestion task %s: %s", job_id, exc)
            if self.request.retries < self.max_retries:
                countdown = DurableJobService.calculate_backoff(self.request.retries + 1)
                job_service.fail_job(job_id, error_message=str(exc), can_retry=True)
                db.commit()
                raise self.retry(exc=exc, countdown=int(countdown)) from exc
            else:
                job_service.fail_job(job_id, error_message=str(exc), can_retry=False)
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
    def process_listing_ingestion_legacy_alias(
        self: Task, job_id_str: str
    ) -> dict[str, Any]:
        """Legacy alias preserved for Phase B6 backwards compatibility."""
        return process_ingestion_canonical(job_id_str)  # type: ignore[call-arg]
