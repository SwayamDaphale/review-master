"""Deterministic evaluation engine service conforming to ADR-0003, ADR-0007, DATA_MODEL.md, and Phase B9 specs.

Ensures:
- Non-LLM, strictly deterministic scoring from published model configurations.
- Evidence-aware: exact evidence version references, trust tiers, and conflict detection.
- Append-only evaluation history: recalculations never overwrite earlier records.
- Missing values remain explicitly missing, never defaulted to zero or assumed matching.
"""

import hashlib
import json
import logging
import uuid
from decimal import Decimal
from typing import Any

from pydantic import ValidationError
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.attribute import VariantAttributeValue
from app.models.evaluation import (
    Evaluation,
    EvaluationModel,
    EvaluationModelVersion,
    ParameterResult,
)
from app.models.evidence import Evidence, EvidenceVersion
from app.models.evidence_quality import EvidenceConflict
from app.models.variant import Variant
from app.schemas.evaluation_config import EvaluationModelConfig
from app.services.evaluation_calculator import DeterministicEvaluationCalculator
from app.services.evaluation_registry import EvaluationRegistryService

logger = logging.getLogger("review_master.evaluation_service")


def _to_json_compatible(val: Any) -> Any:
    """Ensure value can be serialized to JSON/JSONB in PostgreSQL."""
    if val is None:
        return None
    if isinstance(val, Decimal):
        return int(val) if val % 1 == 0 else float(val)
    if isinstance(val, (dict, list)):
        return json.loads(json.dumps(val, default=str))
    return val


class EvaluationFoundationService:
    """Production evaluation engine service providing deterministic scoring, evidence traceability, and append-only history."""

    def __init__(self, db: Session):
        self.db = db
        self.registry = EvaluationRegistryService(db)

    def evaluate_variant(
        self,
        variant_id: uuid.UUID,
        force_model_version_id: uuid.UUID | None = None,
    ) -> Evaluation:
        """Evaluate a canonical variant deterministically against published category evaluation model.

        If category evaluation model is in draft state or uncalibrated, explicitly records
        overall_score=None and confidence_state='unavailable'.
        """
        variant = self.db.get(Variant, variant_id)
        if not variant:
            raise ValueError(f"Variant '{variant_id}' not found.")

        product = variant.product
        category = product.category

        # 1. Resolve Evaluation Model Version
        model_version: EvaluationModelVersion | None = None
        eval_model: EvaluationModel | None = None

        if force_model_version_id:
            model_version = self.db.get(EvaluationModelVersion, force_model_version_id)
            if not model_version:
                raise ValueError(f"Model version '{force_model_version_id}' not found.")
            eval_model = model_version.model
        else:
            # Fetch active published version for category
            active_pair = self.registry.get_active_model_version(category.id)
            if active_pair:
                eval_model, model_version = active_pair
            else:
                # Fallback check for any model version (draft fallback)
                eval_model = self.db.execute(
                    select(EvaluationModel).where(EvaluationModel.category_id == category.id)
                ).scalar_one_or_none()
                if eval_model:
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

        # 2. Gather verified evidence for variant and product
        evidence_records = (
            self.db.execute(
                select(Evidence).where(
                    (Evidence.variant_id == variant.id) | (Evidence.product_id == product.id)
                )
            )
            .scalars()
            .all()
        )
        evidence_map: dict[str, Evidence] = {e.parameter_key: e for e in evidence_records}

        # Gather conflicts
        open_conflicts = (
            self.db.execute(
                select(EvidenceConflict).where(
                    (EvidenceConflict.product_id == product.id) | (EvidenceConflict.variant_id == variant.id),
                    EvidenceConflict.status == "open",
                )
            )
            .scalars()
            .all()
        )
        conflict_keys = {c.parameter_key for c in open_conflicts}

        # 3. Gather canonical attribute values
        attribute_values: dict[str, Any] = {}
        # From Variant configuration JSON
        if variant.configuration:
            for k, v in variant.configuration.items():
                if v is not None:
                    attribute_values[k] = v

        # From VariantAttributeValue table
        vav_records = (
            self.db.execute(
                select(VariantAttributeValue).where(VariantAttributeValue.variant_id == variant.id)
            )
            .scalars()
            .all()
        )
        for vav in vav_records:
            if vav.attribute_definition:
                if vav.value_numeric is not None:
                    attribute_values[vav.attribute_definition.key] = vav.value_numeric
                elif vav.value_boolean is not None:
                    attribute_values[vav.attribute_definition.key] = vav.value_boolean
                elif vav.value_text is not None:
                    attribute_values[vav.attribute_definition.key] = vav.value_text
                elif vav.value_json is not None:
                    attribute_values[vav.attribute_definition.key] = vav.value_json

        # 4. Check if model is valid published configuration
        is_published = model_version is not None and model_version.status == "published"

        # If model is not published or no definition exists, retain draft foundation behavior
        if not is_published or not model_version:
            return self._record_uncalibrated_evaluation(
                variant=variant,
                model_version=model_version,
                evidence_map=evidence_map,
            )

        # 5. Execute Deterministic Evaluation using Published Config
        try:
            model_config = EvaluationModelConfig.model_validate(model_version.definition)
        except (ValidationError, ValueError, TypeError) as exc:
            logger.warning("Published model %s has invalid definition: %s", model_version.id, exc)
            return self._record_uncalibrated_evaluation(
                variant=variant,
                model_version=model_version,
                evidence_map=evidence_map,
                limitation_msg=f"Model definition validation failed: {exc}",
            )

        # Structure evidence records for calculator
        structured_evidence: dict[str, dict[str, Any]] = {}
        for param in model_config.parameters:
            ev = evidence_map.get(param.key) or evidence_map.get(param.attribute_key)
            if ev:
                # Fetch latest version
                latest_ver = (
                    self.db.execute(
                        select(EvidenceVersion)
                        .where(EvidenceVersion.evidence_id == ev.id)
                        .order_by(EvidenceVersion.version.desc())
                    )
                    .scalars()
                    .first()
                )
                structured_evidence[param.key] = {
                    "evidence_id": str(ev.id),
                    "evidence_version_id": str(latest_ver.id) if latest_ver else str(ev.current_version_id),
                    "trust_tier": ev.trust_tier,
                    "verification_state": latest_ver.verification_state if latest_ver else "unverified",
                    "has_conflict": param.key in conflict_keys or param.attribute_key in conflict_keys,
                }
                # If attribute value missing, check latest evidence value
                if param.attribute_key not in attribute_values and latest_ver and latest_ver.value:
                    ev_val = latest_ver.value.get("value")
                    if ev_val is not None:
                        attribute_values[param.attribute_key] = ev_val

        # Execute pure deterministic calculation
        outcome = DeterministicEvaluationCalculator.calculate(
            model_config=model_config,
            attribute_values=attribute_values,
            evidence_records=structured_evidence,
        )

        # 6. Persist Append-Only Evaluation Record
        snapshot_hash = self._compute_evidence_snapshot_hash(evidence_map)
        evaluation = Evaluation(
            variant_id=variant.id,
            model_version_id=model_version.id,
            overall_score=outcome.overall_score,
            confidence_state=outcome.confidence_state,
            confidence_score=outcome.confidence_score,
            coverage=outcome.coverage,
            limitations=outcome.limitations,
            evidence_snapshot_hash=snapshot_hash,
            configuration_hash=outcome.configuration_hash,
            input_fingerprint=outcome.input_fingerprint,
            output_fingerprint=outcome.output_fingerprint,
            calculation_policy_version=outcome.calculation_policy_version,
        )
        self.db.add(evaluation)
        self.db.flush()

        # 7. Persist Parameter Results
        for p_res in outcome.parameter_results:
            param_record = ParameterResult(
                evaluation_id=evaluation.id,
                parameter_key=p_res.parameter_key,
                score=p_res.score,
                status=p_res.status,
                weight=p_res.weight,
                effective_weight=p_res.effective_weight,
                is_critical=p_res.is_critical,
                evidence_ids=p_res.evidence_ids,
                evidence_version_ids=p_res.evidence_version_ids,
                raw_input_value=_to_json_compatible(p_res.raw_input_value),
                normalized_value=_to_json_compatible(p_res.normalized_value),
                scoring_rule=p_res.scoring_rule,
                explanation_data={
                    "explanation": p_res.explanation,
                    "contribution": str(p_res.contribution) if p_res.contribution is not None else None,
                    "limitations": p_res.limitations,
                    "trust_tier": p_res.trust_tier,
                    "verification_state": p_res.verification_state,
                },
            )
            self.db.add(param_record)

        self.db.commit()
        return evaluation

    def _record_uncalibrated_evaluation(
        self,
        variant: Variant,
        model_version: EvaluationModelVersion | None,
        evidence_map: dict[str, Evidence],
        limitation_msg: str | None = None,
    ) -> Evaluation:
        """Record explicit uncalibrated / draft evaluation outcome with overall_score=None."""
        model_def: dict[str, Any] = model_version.definition if model_version else {}
        quality_params: list[dict[str, Any]] = model_def.get("parameters", model_def.get("quality_parameters", []))

        total_params = max(len(quality_params), 1)
        available_params = sum(1 for qp in quality_params if qp.get("key") in evidence_map)
        coverage_dec = Decimal(str(round(available_params / total_params, 3)))

        snapshot_hash = self._compute_evidence_snapshot_hash(evidence_map)
        evaluation = Evaluation(
            variant_id=variant.id,
            model_version_id=model_version.id if model_version else None,
            overall_score=None,
            confidence_state="unavailable",
            confidence_score=Decimal("0.000"),
            coverage=coverage_dec,
            limitations={
                "reason": limitation_msg
                or "Evaluation model is in draft status. Deterministic scoring requires published weights."
            },
            evidence_snapshot_hash=snapshot_hash,
            configuration_hash=model_version.configuration_hash if model_version else None,
        )
        self.db.add(evaluation)
        self.db.flush()

        for qp in quality_params:
            param_key = qp.get("key", "")
            ev_item: Evidence | None = evidence_map.get(param_key)
            param_res = ParameterResult(
                evaluation_id=evaluation.id,
                parameter_key=param_key,
                score=None,
                status="not_scored",
                weight=Decimal(str(qp.get("weight", "0.0"))) if qp.get("weight") else None,
                effective_weight=Decimal("0.0"),
                is_critical=bool(qp.get("critical", False)),
                evidence_ids=[str(ev_item.id)] if ev_item else [],
                evidence_version_ids=[str(ev_item.current_version_id)] if ev_item and ev_item.current_version_id else [],
                explanation_data={
                    "evidence_available": ev_item is not None,
                    "trust_tier": ev_item.trust_tier if ev_item else None,
                },
            )
            self.db.add(param_res)

        self.db.commit()
        return evaluation

    def _compute_evidence_snapshot_hash(self, evidence_map: dict[str, Evidence]) -> str:
        """Compute SHA-256 evidence snapshot hash for determinism audit."""
        snapshot_tokens: list[str] = []
        for k in sorted(evidence_map.keys()):
            ev = evidence_map[k]
            snapshot_tokens.append(f"{k}:{ev.current_version_id}:{ev.trust_tier}")
        return hashlib.sha256(";".join(snapshot_tokens).encode("utf-8")).hexdigest()
