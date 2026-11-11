"""Background tasks for evidence quality management, trust tier evaluation, and conflict detection."""

import logging
import uuid
from typing import Any

from celery import Celery, Task  # type: ignore[import-untyped]
from sqlalchemy import select

import app.worker.celery_app as ca
from app.models.evidence import Evidence, EvidenceVersion
from app.services.evidence_service import EvidenceService
from app.worker.services.job_service import DurableJobService

logger = logging.getLogger("review_master.tasks.evidence")


def register_evidence_tasks(celery_app: Celery) -> None:
    """Register evidence quality and provenance tasks."""

    @celery_app.task(
        bind=True,
        name="evidence.assign_trust",
        max_retries=3,
        default_retry_delay=5,
    )
    def assign_evidence_trust(
        self: Task,
        evidence_id_str: str,
        source_type: str,
        client_trust_tier: int | None = None,
        job_id_str: str | None = None,
    ) -> dict[str, Any]:
        """Assign backend-controlled trust tier to an evidence record, ignoring client claims."""
        job_id = uuid.UUID(job_id_str) if job_id_str else None
        evidence_id = uuid.UUID(evidence_id_str)
        db = ca.SessionLocal()
        try:
            job_service = DurableJobService(db)
            if job_id:
                job_service.start_job(job_id, worker_id=getattr(self.request, "hostname", None))
                db.commit()

            ev = db.get(Evidence, evidence_id)
            if not ev:
                raise ValueError(f"Evidence {evidence_id} not found.")

            computed_tier = EvidenceService.determine_trust_tier(
                source_type=source_type,
                client_claimed_tier=client_trust_tier,
            )
            ev.trust_tier = computed_tier
            db.commit()

            result_payload = {
                "evidence_id": str(ev.id),
                "trust_tier": ev.trust_tier,
                "status": "completed",
            }

            if job_id:
                job_service.complete_job(job_id, result_payload=result_payload)
                db.commit()

            return result_payload
        except Exception as exc:
            logger.error("Error assigning trust tier to evidence %s: %s", evidence_id_str, exc)
            if job_id:
                job_service.fail_job(job_id, error_message=str(exc))
                db.commit()
            raise
        finally:
            db.close()

    @celery_app.task(
        bind=True,
        name="evidence.detect_conflicts",
        max_retries=2,
        default_retry_delay=10,
    )
    def detect_conflicts_for_target(
        self: Task,
        product_id_str: str | None = None,
        variant_id_str: str | None = None,
        job_id_str: str | None = None,
    ) -> dict[str, Any]:
        """Scan evidence records for a product or variant and identify conflicting attribute values."""
        job_id = uuid.UUID(job_id_str) if job_id_str else None
        prod_id = uuid.UUID(product_id_str) if product_id_str else None
        var_id = uuid.UUID(variant_id_str) if variant_id_str else None

        db = ca.SessionLocal()
        try:
            job_service = DurableJobService(db)
            if job_id:
                job_service.start_job(job_id, worker_id=getattr(self.request, "hostname", None))
                db.commit()

            ev_service = EvidenceService(db)
            stmt = select(Evidence)
            if var_id:
                stmt = stmt.where(Evidence.variant_id == var_id)
            elif prod_id:
                stmt = stmt.where(Evidence.product_id == prod_id)

            evidence_items = db.execute(stmt).scalars().all()
            conflicts_found = 0

            for ev in evidence_items:
                versions = (
                    db.execute(
                        select(EvidenceVersion)
                        .where(EvidenceVersion.evidence_id == ev.id)
                        .order_by(EvidenceVersion.version.asc())
                    )
                    .scalars()
                    .all()
                )
                if len(versions) >= 2:
                    for i in range(len(versions) - 1):
                        v1 = versions[i]
                        v2 = versions[i + 1]
                        conflict = ev_service._detect_and_record_conflict(
                            ev=ev,
                            existing_version=v1,
                            new_val_payload=v2.value,
                            new_unit=v2.unit,
                            product_id=prod_id,
                            variant_id=var_id,
                        )
                        if conflict:
                            conflicts_found += 1

            db.commit()
            result_payload = {
                "conflicts_detected": conflicts_found,
                "evidence_checked": len(evidence_items),
                "status": "completed",
            }

            if job_id:
                job_service.complete_job(job_id, result_payload=result_payload)
                db.commit()

            return result_payload
        except Exception as exc:
            logger.error("Error detecting conflicts: %s", exc)
            if job_id:
                job_service.fail_job(job_id, error_message=str(exc))
                db.commit()
            raise
        finally:
            db.close()

