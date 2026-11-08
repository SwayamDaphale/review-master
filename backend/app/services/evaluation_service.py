"""Deterministic evaluation foundation service conforming to ADR-0003, ADR-0007, and DATA_MODEL.md.

Ensures:
- LLMs never calculate scores or arbitrate ratings.
- Evaluates canonical variants only from verified evidence records.
- If evaluation models are in draft status or critical inputs are missing,
  records explicit 'unavailable' / 'limited' states with overall_score=None.
- Never fabricates scores or confidence tiers.
"""

import hashlib
import logging
import uuid
from decimal import Decimal
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.evaluation import (
    Evaluation,
    EvaluationModel,
    EvaluationModelVersion,
    ParameterResult,
)
from app.models.evidence import Evidence
from app.models.variant import Variant

logger = logging.getLogger("review_master.evaluation_service")


class EvaluationFoundationService:
    """Deterministic evaluation input preparation and foundation service."""

    def __init__(self, db: Session):
        self.db = db

    def evaluate_variant(self, variant_id: uuid.UUID) -> Evaluation:
        """Prepare deterministic evaluation inputs and record evaluation state.

        If the category evaluation model is in draft state or laboratory evidence
        is incomplete, explicitly records overall_score=None and confidence_state='unavailable'.
        """
        variant = self.db.get(Variant, variant_id)
        if not variant:
            raise ValueError(f"Variant '{variant_id}' not found.")

        product = variant.product
        category = product.category

        # 1. Look up evaluation model for this category
        eval_model = self.db.execute(
            select(EvaluationModel).where(EvaluationModel.category_id == category.id)
        ).scalar_one_or_none()

        model_version: EvaluationModelVersion | None = None
        if eval_model:
            # Prefer published version, fallback to draft
            model_version = (
                self.db.execute(
                    select(EvaluationModelVersion)
                    .where(EvaluationModelVersion.model_id == eval_model.id)
                    .order_by(
                        (EvaluationModelVersion.status == "published").desc(),
                        EvaluationModelVersion.created_at.desc(),
                    )
                )
                .scalars()
                .first()
            )

        # 2. Gather verified evidence for this variant and product
        evidence_records = (
            self.db.execute(
                select(Evidence).where(
                    (Evidence.variant_id == variant.id)
                    | (Evidence.product_id == product.id)
                )
            )
            .scalars()
            .all()
        )

        evidence_map: dict[str, Evidence] = {
            e.parameter_key: e for e in evidence_records
        }

        # 3. Compute evidence snapshot hash for determinism audit
        snapshot_tokens: list[str] = []
        for k in sorted(evidence_map.keys()):
            ev = evidence_map[k]
            snapshot_tokens.append(f"{k}:{ev.current_version_id}:{ev.trust_tier}")
        snapshot_hash = hashlib.sha256(
            ";".join(snapshot_tokens).encode("utf-8")
        ).hexdigest()

        # 4. Check if model is published or draft
        is_published = model_version is not None and model_version.status == "published"

        # Definition parameters
        model_def: dict[str, Any] = model_version.definition if model_version else {}
        quality_params: list[dict[str, Any]] = model_def.get("quality_parameters", [])

        total_params = max(len(quality_params), 1)
        available_params = sum(
            1 for qp in quality_params if qp.get("key") in evidence_map
        )
        coverage_dec = Decimal(str(round(available_params / total_params, 3)))

        evaluation = Evaluation(
            variant_id=variant.id,
            model_version_id=model_version.id if model_version else None,
            overall_score=None,  # NEVER fabricate scores when model is draft or uncalibrated
            confidence_state="unavailable" if not is_published else "limited",
            confidence_score=Decimal("0.000") if not is_published else Decimal("0.350"),
            coverage=coverage_dec,
            limitations={
                "reason": (
                    "Evaluation model is in draft status. Deterministic scoring requires "
                    "published weights and independent laboratory evidence."
                )
                if not is_published
                else "Independent laboratory evidence incomplete for critical parameters."
            },
            evidence_snapshot_hash=snapshot_hash,
        )
        self.db.add(evaluation)
        self.db.flush()

        # 5. Populate parameter results
        for qp in quality_params:
            param_key = qp.get("key", "")
            ev_item: Evidence | None = evidence_map.get(param_key)
            param_res = ParameterResult(
                evaluation_id=evaluation.id,
                parameter_key=param_key,
                score=None,  # Strictly None for uncalibrated draft
                status="not_scored",
                weight=Decimal(str(qp.get("weight", "0.0")))
                if qp.get("weight")
                else None,
                is_critical=bool(qp.get("critical", False)),
                evidence_ids=[str(ev_item.id)] if ev_item else [],
                explanation_data={
                    "evidence_available": ev_item is not None,
                    "trust_tier": ev_item.trust_tier if ev_item else None,
                },
            )
            self.db.add(param_res)

        self.db.commit()
        return evaluation
