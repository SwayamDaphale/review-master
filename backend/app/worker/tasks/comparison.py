"""Background tasks for product and variant comparison data preparation."""

import logging
import uuid
from typing import Any

from celery import Celery, Task  # type: ignore[import-untyped]
from sqlalchemy import select

import app.worker.celery_app as ca
from app.models.attribute import AttributeDefinition, VariantAttributeValue
from app.models.comparison import ComparisonItem, ComparisonSession
from app.models.variant import Variant
from app.worker.services.job_service import DurableJobService

logger = logging.getLogger("review_master.tasks.comparison")


def register_comparison_tasks(celery_app: Celery) -> None:
    """Register comparison preparation tasks."""

    @celery_app.task(
        bind=True,
        name="comparison.prepare",
        max_retries=3,
        default_retry_delay=5,
    )
    def prepare_comparison(
        self: Task,
        session_id_str: str,
        job_id_str: str | None = None,
    ) -> dict[str, Any]:
        """Precompute and assemble comparison matrices for active comparison session."""
        session_id = uuid.UUID(session_id_str)
        job_id = uuid.UUID(job_id_str) if job_id_str else None
        db = ca.SessionLocal()
        try:
            job_service = DurableJobService(db)
            if job_id:
                job_service.start_job(job_id, worker_id=getattr(self.request, "hostname", None))
                db.commit()

            session = db.get(ComparisonSession, session_id)
            if not session:
                err = f"Comparison session {session_id} not found."
                if job_id:
                    job_service.fail_job(job_id, err, can_retry=False)
                    db.commit()
                return {"error": err, "status": "failed"}

            items = db.execute(
                select(ComparisonItem).where(ComparisonItem.session_id == session_id)
            ).scalars().all()

            compared_data: list[dict[str, Any]] = []
            for item in items:
                variant_info: dict[str, Any] = {"item_id": str(item.id), "attributes": {}}
                if item.variant_id:
                    variant = db.get(Variant, item.variant_id)
                    if variant:
                        variant_info["sku_label"] = variant.sku_label
                        stmt = select(VariantAttributeValue).where(
                            VariantAttributeValue.variant_id == variant.id
                        )
                        avs = db.execute(stmt).scalars().all()
                        for av in avs:
                            adef = db.get(AttributeDefinition, av.attribute_id)
                            k = adef.key if adef else str(av.attribute_id)
                            variant_info["attributes"][k] = {
                                "value": float(av.value_numeric) if av.value_numeric is not None else av.raw_value,
                                "unit": av.canonical_unit,
                            }
                compared_data.append(variant_info)

            result_payload = {
                "session_id": str(session_id),
                "item_count": len(compared_data),
                "items": compared_data,
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
            logger.error("Error preparing comparison for session %s: %s", session_id, exc)
            if job_id:
                job_service.fail_job(job_id, error_message=str(exc))
                db.commit()
            raise
        finally:
            db.close()
