"""Background tasks for deterministic product and variant evaluation."""

import logging
import uuid
from typing import Any

from celery import Celery, Task  # type: ignore[import-untyped]

import app.worker.celery_app as ca
from app.services.evaluation_service import EvaluationFoundationService
from app.worker.services.job_service import DurableJobService

logger = logging.getLogger("review_master.tasks.evaluation")


def register_evaluation_tasks(celery_app: Celery) -> None:
    """Register evaluation engine calculation tasks."""

    @celery_app.task(
        bind=True,
        name="evaluation.calculate",
        max_retries=3,
        default_retry_delay=5,
    )
    def calculate_evaluation(
        self: Task,
        variant_id_str: str,
        job_id_str: str | None = None,
    ) -> dict[str, Any]:
        """Compute deterministic evaluation score for variant."""
        variant_id = uuid.UUID(variant_id_str)
        job_id = uuid.UUID(job_id_str) if job_id_str else None
        db = ca.SessionLocal()
        try:
            job_service = DurableJobService(db)
            if job_id:
                job_service.start_job(job_id, worker_id=getattr(self.request, "hostname", None))
                db.commit()

            service = EvaluationFoundationService(db)
            evaluation = service.evaluate_variant(variant_id)
            db.commit()

            result_payload = {
                "variant_id": str(variant_id),
                "evaluation_id": str(evaluation.id),
                "overall_score": float(evaluation.overall_score) if evaluation.overall_score is not None else None,
                "confidence_state": evaluation.confidence_state,
                "status": "completed",
            }

            if job_id:
                job_service.complete_job(job_id, result_payload=result_payload)
                db.commit()

            return result_payload

        except Exception as exc:
            from celery.exceptions import Retry  # type: ignore[import-untyped]

            if isinstance(exc, Retry):
                raise
            logger.error("Error calculating evaluation for variant %s: %s", variant_id, exc)
            if job_id:
                job_service.fail_job(job_id, error_message=str(exc))
                db.commit()
            raise
        finally:
            db.close()
