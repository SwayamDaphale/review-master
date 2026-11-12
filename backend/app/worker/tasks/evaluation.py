"""Background tasks for deterministic product and variant evaluation conforming to ADR-0003 and Phase B9 specs."""

import logging
import uuid
from typing import Any

from celery import Celery, Task  # type: ignore[import-untyped]

import app.worker.celery_app as ca
from app.services.evaluation_service import EvaluationFoundationService
from app.worker.services.job_service import DurableJobService

logger = logging.getLogger("review_master.tasks.evaluation")


def register_evaluation_tasks(celery_app: Celery) -> None:
    """Register deterministic evaluation engine calculation tasks."""

    @celery_app.task(
        bind=True,
        name="evaluation.calculate",
        max_retries=3,
        default_retry_delay=5,
    )
    def calculate_evaluation(
        self: Task,
        variant_id_str: str,
        model_version_id_str: str | None = None,
        job_id_str: str | None = None,
    ) -> dict[str, Any]:
        """Compute deterministic evaluation score for variant."""
        variant_id = uuid.UUID(variant_id_str)
        model_version_id = uuid.UUID(model_version_id_str) if model_version_id_str else None
        job_id = uuid.UUID(job_id_str) if job_id_str else None
        db = ca.SessionLocal()
        try:
            job_service = DurableJobService(db)
            if job_id:
                job_service.start_job(job_id, worker_id=getattr(self.request, "hostname", None))
                db.commit()

            service = EvaluationFoundationService(db)
            evaluation = service.evaluate_variant(
                variant_id=variant_id,
                force_model_version_id=model_version_id,
            )
            db.commit()

            result_payload = {
                "variant_id": str(variant_id),
                "evaluation_id": str(evaluation.id),
                "model_version_id": str(evaluation.model_version_id) if evaluation.model_version_id else None,
                "overall_score": float(evaluation.overall_score) if evaluation.overall_score is not None else None,
                "coverage": float(evaluation.coverage) if evaluation.coverage is not None else None,
                "confidence_score": float(evaluation.confidence_score) if evaluation.confidence_score is not None else None,
                "confidence_state": evaluation.confidence_state,
                "output_fingerprint": evaluation.output_fingerprint,
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

    @celery_app.task(
        bind=True,
        name="evaluation.recalculate",
        max_retries=3,
        default_retry_delay=5,
    )
    def recalculate_evaluation(
        self: Task,
        variant_id_str: str,
        model_version_id_str: str | None = None,
        job_id_str: str | None = None,
    ) -> dict[str, Any]:
        """Recalculate evaluation for a variant, strictly appending a new immutable evaluation record."""
        return calculate_evaluation(
            variant_id_str=variant_id_str,
            model_version_id_str=model_version_id_str,
            job_id_str=job_id_str,
        )
