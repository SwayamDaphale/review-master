"""Deterministic ranking engine and evidence-grounded explanation generator."""

import hashlib
import json
import uuid
from decimal import Decimal
from typing import Any

from app.models.evaluation import Evaluation
from app.models.variant import Variant
from app.schemas.recommendation import (
    CandidateEvaluationOutcome,
    ParsedRequirements,
    RecommendedProductItem,
)


def _to_float(val: Any) -> float | None:
    if val is None:
        return None
    if isinstance(val, (int, float)):
        return float(val)
    if isinstance(val, Decimal):
        return float(val)
    return None


class RecommendationRankingService:
    """Deterministic ranking and evidence-traceable explanation generator for eligible products."""

    RANKING_POLICY_VERSION = "v1"

    @classmethod
    def rank_and_explain(
        cls,
        *,
        requirements: ParsedRequirements,
        eligible_outcomes: list[CandidateEvaluationOutcome],
        evaluations_map: dict[uuid.UUID, Evaluation],
        variants_map: dict[uuid.UUID, Variant],
        offers_map: dict[uuid.UUID, dict[str, Any]],
        community_map: dict[uuid.UUID, str | None],
        limit: int = 5,
    ) -> list[RecommendedProductItem]:
        """Sort eligible candidates using deterministic multi-tier tie breaking and generate explanations."""
        scored_candidates: list[dict[str, Any]] = []

        for outcome in eligible_outcomes:
            var_id = outcome.variant_id
            variant = variants_map.get(var_id)
            if not variant:
                continue

            evaluation = evaluations_map.get(var_id)
            offer = offers_map.get(var_id, {})
            comm_summary = community_map.get(var_id)

            score_val = _to_float(evaluation.overall_score) if evaluation else None
            coverage_val = _to_float(evaluation.coverage) if evaluation else None
            confidence_val = _to_float(evaluation.confidence_score) if evaluation else None

            scored_candidates.append(
                {
                    "outcome": outcome,
                    "variant": variant,
                    "evaluation": evaluation,
                    "offer": offer,
                    "community_summary": comm_summary,
                    # Tie-breaking keys
                    "score": score_val if score_val is not None else -1.0,
                    "coverage": coverage_val if coverage_val is not None else -1.0,
                    "confidence": confidence_val if confidence_val is not None else -1.0,
                    "variant_id_str": str(var_id),
                }
            )

        # Multi-tier deterministic sorting:
        # 1. Overall Score (descending)
        # 2. Coverage (descending)
        # 3. Confidence Score (descending)
        # 4. Canonical Variant UUID (ascending) for stable tie-breaking
        scored_candidates.sort(
            key=lambda item: (
                -item["score"],
                -item["coverage"],
                -item["confidence"],
                item["variant_id_str"],
            )
        )

        ranked_results: list[RecommendedProductItem] = []
        for idx, item in enumerate(scored_candidates[:limit], start=1):
            outcome = item["outcome"]
            variant = item["variant"]
            evaluation = item["evaluation"]
            offer = item["offer"]
            comm_summary = item["community_summary"]

            # Generate evidence-grounded explanation
            explanation, exp_evidence = cls._build_explanation(
                rank=idx,
                outcome=outcome,
                evaluation=evaluation,
                offer=offer,
                requirements=requirements,
            )

            # Verified specifications mapping
            verified_specs: dict[str, Any] = {}
            for c in outcome.constraints:
                if c.actual_value is not None:
                    verified_specs[c.attribute_key] = {
                        "value": c.actual_value,
                        "unit": c.unit,
                        "outcome": c.outcome.value,
                    }

            rec_item = RecommendedProductItem(
                rank=idx,
                variant_id=variant.id,
                product_id=variant.product_id,
                product_name=variant.product.name,
                manufacturer=variant.product.manufacturer,
                sku_label=variant.sku_label,
                overall_score=_to_float(evaluation.overall_score) if evaluation else None,
                confidence_state=evaluation.confidence_state if evaluation else "unavailable",
                confidence_score=_to_float(evaluation.confidence_score) if evaluation else None,
                coverage=_to_float(evaluation.coverage) if evaluation else None,
                current_price=offer.get("price"),
                currency=offer.get("currency", "INR"),
                evaluation_id=evaluation.id if evaluation else None,
                model_version_id=evaluation.model_version_id if evaluation else None,
                model_version=evaluation.model_version.version if evaluation and evaluation.model_version else None,
                explanation=explanation,
                explanation_evidence=exp_evidence,
                verified_specifications=verified_specs,
                community_summary=comm_summary,
            )
            ranked_results.append(rec_item)

        return ranked_results

    @classmethod
    def _build_explanation(
        cls,
        rank: int,
        outcome: CandidateEvaluationOutcome,
        evaluation: Evaluation | None,
        offer: dict[str, Any],
        requirements: ParsedRequirements,
    ) -> tuple[str, dict[str, Any]]:
        """Generate deterministic, evidence-grounded natural explanation referencing verified specs."""
        parts: list[str] = []
        evidence_refs: dict[str, Any] = {
            "evaluation_id": str(evaluation.id) if evaluation else None,
            "model_version": evaluation.model_version.version if evaluation and evaluation.model_version else None,
            "passed_constraints": [],
        }

        # 1. Quality & Score statement
        if evaluation and evaluation.overall_score is not None:
            score_f = float(evaluation.overall_score)
            parts.append(
                f"Ranked #{rank} with an evaluation score of {score_f:.1f}/100 ({evaluation.confidence_state} confidence)."
            )
        else:
            parts.append(
                f"Ranked #{rank} based on verified constraint eligibility (evaluation score is currently uncalibrated)."
            )

        # 2. Hard Constraints satisfaction statement
        passed_clauses = []
        for c in outcome.constraints:
            if c.attribute_key == "price" and c.actual_value is not None:
                passed_clauses.append(f"budget (₹{c.actual_value:,.0f} <= ₹{c.target_value:,.0f})")
            elif c.actual_value is not None:
                passed_clauses.append(
                    f"{c.attribute_key.upper()} ({c.actual_value} {c.unit or ''})"
                )
            evidence_refs["passed_constraints"].append(
                {
                    "attribute_key": c.attribute_key,
                    "target": c.target_value,
                    "actual": c.actual_value,
                    "unit": c.unit,
                }
            )

        if passed_clauses:
            parts.append(f"Meets all required hard constraints: {', '.join(passed_clauses)}.")

        # 3. Commercial offer highlight
        if offer.get("price") is not None:
            parts.append(f"Current verified offer: ₹{offer['price']:,.0f} {offer.get('currency', 'INR')}.")

        # 4. Limitations or low confidence notice
        if evaluation and evaluation.confidence_state in ("low", "very_low"):
            parts.append(
                f"Notice: Evaluation has limited coverage ({float(evaluation.coverage or 0):.0%}), some secondary evidence was missing."
            )

        return " ".join(parts), evidence_refs

    @staticmethod
    def compute_fingerprints(
        requirements: ParsedRequirements,
        ranked_items: list[RecommendedProductItem],
        excluded_count: int,
    ) -> tuple[str, str]:
        """Compute deterministic input and output fingerprints for reproducibility audit."""
        input_payload = {
            "category": requirements.category_key,
            "budget": requirements.budget_max,
            "currency": requirements.budget_currency,
            "hard_constraints": [
                {"key": hc.attribute_key, "op": hc.operator, "val": str(hc.target_value)}
                for hc in sorted(requirements.hard_constraints, key=lambda x: x.attribute_key)
            ],
            "excluded_brands": sorted(requirements.excluded_brands),
            "parser_version": requirements.parser_version,
        }
        input_json = json.dumps(input_payload, sort_keys=True, ensure_ascii=True)
        input_hash = hashlib.sha256(input_json.encode("utf-8")).hexdigest()

        output_payload = {
            "ranked": [
                {
                    "rank": item.rank,
                    "variant_id": str(item.variant_id),
                    "score": item.overall_score,
                }
                for item in ranked_items
            ],
            "excluded_count": excluded_count,
            "ranking_policy_version": RecommendationRankingService.RANKING_POLICY_VERSION,
        }
        output_json = json.dumps(output_payload, sort_keys=True, ensure_ascii=True)
        output_hash = hashlib.sha256(output_json.encode("utf-8")).hexdigest()

        return input_hash, output_hash

