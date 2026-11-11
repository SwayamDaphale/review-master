"""Background tasks for identity resolution and catalog entity linkage."""

import logging
import uuid
from typing import Any

from celery import Celery, Task  # type: ignore[import-untyped]
from sqlalchemy import select

import app.worker.celery_app as ca
from app.contracts.extraction.canonical import CanonicalInternalExtraction
from app.db.base import utc_now
from app.models.category import Category
from app.models.identity_mapping import IdentityReviewQueue
from app.models.marketplace import Marketplace
from app.services.identity_resolver import IdentityResolver
from app.worker.services.job_service import DurableJobService

logger = logging.getLogger("review_master.tasks.identity")


def register_identity_tasks(celery_app: Celery) -> None:
    """Register identity resolution tasks."""

    @celery_app.task(
        bind=True,
        name="identity.resolve",
        max_retries=3,
        default_retry_delay=5,
    )
    def resolve_product_identity(
        self: Task,
        marketplace_code: str,
        asin: str,
        title: str | None = None,
        brand: str | None = None,
        model_name: str | None = None,
        job_id_str: str | None = None,
    ) -> dict[str, Any]:
        """Resolve canonical product and variant identities from marketplace signals using 5-stage pipeline."""
        job_id = uuid.UUID(job_id_str) if job_id_str else None
        db = ca.SessionLocal()
        try:
            job_service = DurableJobService(db)
            if job_id:
                job_service.start_job(job_id, worker_id=getattr(self.request, "hostname", None))
                db.commit()

            # 1. Resolve marketplace entity
            mp = db.execute(
                select(Marketplace).where(Marketplace.key == marketplace_code)
            ).scalar_one_or_none()
            if not mp:
                mp = Marketplace(
                    key=marketplace_code,
                    name=marketplace_code.capitalize(),
                    adapter="generic",
                )
                db.add(mp)
                db.flush()

            # 2. Resolve default category if needed
            cat = db.execute(
                select(Category).where(Category.key == "smartphone")
            ).scalar_one_or_none()
            if not cat:
                cat = Category(key="smartphone", name="Smartphones")
                db.add(cat)
                db.flush()

            # 3. Construct canonical extraction envelope for resolver
            canonical = CanonicalInternalExtraction(
                ingestion_record_id=f"rec-{uuid.uuid4()}",
                source_contract="generalized_v1",
                source_schema_version="1.0.0",
                marketplace=marketplace_code,
                product_category="smartphone",
                product_url=f"https://{marketplace_code}/dp/{asin}",
                extraction_method="background_identity_task",
                extension_version="1.0.0",
                extracted_at=utc_now(),
                asin=asin,
                raw_title=title or asin,
                normalized_brand=brand or "Generic",
                normalized_model_name=model_name or asin,
            )

            resolver = IdentityResolver(db)
            resolution = resolver.resolve_canonical(
                marketplace_id=mp.id,
                asin=asin,
                canonical=canonical,
                auto_queue_review=True,
            )
            db.commit()

            result_payload = {
                "product_id": str(resolution.product_id) if resolution.product_id else None,
                "variant_id": str(resolution.variant_id) if resolution.variant_id else None,
                "match_type": resolution.match_state,
                "confidence": resolution.confidence,
                "review_queue_id": str(resolution.review_queue_id) if resolution.review_queue_id else None,
                "candidate_scores": resolution.candidate_scores,
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
            logger.error("Error resolving identity for %s/%s: %s", marketplace_code, asin, exc)
            if job_id:
                job_service.fail_job(job_id, error_message=str(exc))
                db.commit()
            raise
        finally:
            db.close()

    @celery_app.task(
        bind=True,
        name="identity.review_candidates",
        max_retries=2,
        default_retry_delay=10,
    )
    def review_pending_candidates(
        self: Task,
        limit: int = 50,
        job_id_str: str | None = None,
    ) -> dict[str, Any]:
        """Process pending items in the IdentityReviewQueue."""
        job_id = uuid.UUID(job_id_str) if job_id_str else None
        db = ca.SessionLocal()
        try:
            job_service = DurableJobService(db)
            if job_id:
                job_service.start_job(job_id, worker_id=getattr(self.request, "hostname", None))
                db.commit()

            items = (
                db.execute(
                    select(IdentityReviewQueue)
                    .where(IdentityReviewQueue.status == "pending")
                    .limit(limit)
                )
                .scalars()
                .all()
            )

            processed_count = len(items)
            result_payload = {
                "pending_count": processed_count,
                "status": "completed",
            }

            if job_id:
                job_service.complete_job(job_id, result_payload=result_payload)
                db.commit()

            return result_payload
        except Exception as exc:
            logger.error("Error processing identity review queue: %s", exc)
            if job_id:
                job_service.fail_job(job_id, error_message=str(exc))
                db.commit()
            raise
        finally:
            db.close()
