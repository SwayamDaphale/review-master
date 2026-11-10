"""Background tasks for attribute normalization and AI-driven enrichment."""

import asyncio
import logging
import uuid
from typing import Any

from celery import Celery, Task  # type: ignore[import-untyped]
from sqlalchemy import select

import app.worker.celery_app as ca
from app.core.config import settings
from app.core.units import UnitNormalizer
from app.models.attribute import AttributeDefinition, VariantAttributeValue
from app.models.variant import Variant
from app.schemas.ai_extraction import EnrichedProductAttributes
from app.services.llm.orchestrator import InferenceOrchestrator
from app.worker.services.job_service import DurableJobService

logger = logging.getLogger("review_master.tasks.attributes")


def register_attribute_tasks(celery_app: Celery) -> None:
    """Register attribute normalization and enrichment tasks."""

    @celery_app.task(
        bind=True,
        name="attributes.normalize",
        max_retries=3,
        default_retry_delay=5,
    )
    def normalize_attributes(
        self: Task,
        variant_id_str: str,
        job_id_str: str | None = None,
    ) -> dict[str, Any]:
        """Normalize physical dimensions and units for variant attributes."""
        variant_id = uuid.UUID(variant_id_str)
        job_id = uuid.UUID(job_id_str) if job_id_str else None
        db = ca.SessionLocal()
        try:
            job_service = DurableJobService(db)
            if job_id:
                job_service.start_job(job_id, worker_id=getattr(self.request, "hostname", None))
                db.commit()

            variant = db.get(Variant, variant_id)
            if not variant:
                err = f"Variant {variant_id} not found."
                if job_id:
                    job_service.fail_job(job_id, err, can_retry=False)
                    db.commit()
                return {"error": err, "status": "failed"}

            stmt = select(VariantAttributeValue).where(
                VariantAttributeValue.variant_id == variant_id
            )
            attr_values = db.execute(stmt).scalars().all()
            normalized_results: list[dict[str, Any]] = []

            for av in attr_values:
                attr_def = db.get(AttributeDefinition, av.attribute_id)
                unit_to_use = av.original_unit or (attr_def.canonical_unit if attr_def else None)
                val_to_use = av.value_numeric or av.raw_value

                if val_to_use is not None:
                    import re
                    val_str = str(val_to_use).strip()
                    m = re.search(r"[-+]?\d*\.?\d+", val_str)
                    numeric_part = m.group(0) if m else val_str
                    res = UnitNormalizer.normalize(numeric_part, unit_to_use)
                    if res.is_valid and res.canonical_value is not None:
                        av.value_numeric = res.canonical_value
                        av.canonical_unit = res.canonical_unit
                        normalized_results.append(
                            {
                                "attribute_key": attr_def.key if attr_def else "unknown",
                                "raw_value": av.raw_value,
                                "canonical_value": float(res.canonical_value),
                                "canonical_unit": res.canonical_unit,
                                "dimension": res.dimension,
                            }
                        )

            db.commit()
            result_payload = {
                "variant_id": str(variant_id),
                "normalized_count": len(normalized_results),
                "attributes": normalized_results,
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
            logger.error("Error normalizing attributes for variant %s: %s", variant_id, exc)
            if job_id:
                job_service.fail_job(job_id, error_message=str(exc))
                db.commit()
            raise
        finally:
            db.close()

    @celery_app.task(
        bind=True,
        name="attributes.enrich",
        max_retries=3,
        default_retry_delay=5,
    )
    def enrich_attributes(
        self: Task,
        raw_text: str,
        variant_id_str: str | None = None,
        source_evidence_id_str: str | None = None,
        job_id_str: str | None = None,
    ) -> dict[str, Any]:
        """Perform AI-driven structured attribute enrichment with strict grounding."""
        job_id = uuid.UUID(job_id_str) if job_id_str else None
        source_evidence_id: uuid.UUID | None = None
        if source_evidence_id_str is not None:
            clean_ev_id = source_evidence_id_str.strip()
            if not clean_ev_id:
                raise ValueError("Invalid evidence ID: empty identifier.")
            try:
                source_evidence_id = uuid.UUID(clean_ev_id)
            except (ValueError, TypeError) as exc:
                raise ValueError(f"Invalid evidence ID format: {source_evidence_id_str}") from exc

        db = ca.SessionLocal()
        try:
            job_service = DurableJobService(db)
            if job_id:
                job_service.start_job(job_id, worker_id=getattr(self.request, "hostname", None))
                db.commit()

            orchestrator = InferenceOrchestrator(
                fallback_enabled=settings.LLM_FALLBACK_ENABLED,
                max_retries=settings.LLM_MAX_RETRIES,
                timeout=settings.LLM_TIMEOUT_SECONDS,
            )

            prompt = (
                f"Extract structured product attributes from the following raw product text. "
                f"Ground all extracted attributes with source quotes from the text:\n\n{raw_text}"
            )

            extraction_result = asyncio.run(
                orchestrator.generate_structured(
                    prompt=prompt,
                    schema=EnrichedProductAttributes,
                    system_prompt=(
                        "You are a strict catalog extraction engine. "
                        "Only extract facts explicitly stated in the source text."
                    ),
                )
            )

            enriched_data = extraction_result.data.model_dump()
            result_payload = {
                "variant_id": variant_id_str,
                "source_evidence_id": str(source_evidence_id) if source_evidence_id else None,
                "provider": extraction_result.provider,
                "model": extraction_result.model,
                "data": enriched_data,
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
            logger.error("Error enriching attributes: %s", exc)
            if job_id:
                job_service.fail_job(job_id, error_message=str(exc))
                db.commit()
            raise
        finally:
            db.close()
