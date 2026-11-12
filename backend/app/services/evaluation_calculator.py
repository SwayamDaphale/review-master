"""Deterministic evaluation calculator implementing weight normalization, coverage, confidence, and evidence traceability."""

import hashlib
import json
from dataclasses import dataclass, field
from decimal import ROUND_HALF_UP, Decimal
from typing import Any

from app.schemas.evaluation_config import (
    BooleanRuleParams,
    EvaluationModelConfig,
    LinearRangeRuleParams,
    OrdinalRuleParams,
    ParameterConfig,
    PiecewiseRuleParams,
    compute_configuration_hash,
)
from app.services.evaluation_rules import (
    evaluate_boolean,
    evaluate_linear_range,
    evaluate_ordinal,
    evaluate_piecewise,
)

CALC_PRECISION = Decimal("0.0001")


@dataclass
class ParameterEvaluationOutcome:
    """Deterministic evaluation outcome for a single parameter."""

    parameter_key: str
    attribute_key: str
    label: str
    weight: Decimal
    effective_weight: Decimal
    score: Decimal | None
    status: str  # "evaluated", "missing", "conflicting", "unverified", "rejected", "superseded", "invalid"
    scoring_rule: str
    raw_input_value: Any | None
    normalized_value: Any | None
    contribution: Decimal | None
    is_critical: bool
    evidence_ids: list[str] = field(default_factory=list)
    evidence_version_ids: list[str] = field(default_factory=list)
    limitations: list[str] = field(default_factory=list)
    explanation: str = ""
    trust_tier: int | None = None
    verification_state: str | None = None


@dataclass
class EvaluationCalculationOutcome:
    """Full deterministic evaluation result envelope."""

    overall_score: Decimal | None
    coverage: Decimal
    coverage_state: str  # "sufficient" | "insufficient"
    confidence_score: Decimal
    confidence_state: str  # "high" | "medium" | "low" | "insufficient_evidence"
    limitations: dict[str, Any]
    parameter_results: list[ParameterEvaluationOutcome]
    configuration_hash: str
    input_fingerprint: str
    output_fingerprint: str
    calculation_policy_version: str = "v1"


class DeterministicEvaluationCalculator:
    """Pure deterministic calculation engine for product evaluations."""

    @classmethod
    def calculate(
        cls,
        model_config: EvaluationModelConfig,
        attribute_values: dict[str, Any],
        evidence_records: dict[str, dict[str, Any]],
    ) -> EvaluationCalculationOutcome:
        """Calculate deterministic evaluation from validated model configuration and evidence.

        Args:
            model_config: Validated published EvaluationModelConfig.
            attribute_values: Mapping of attribute_key -> observed value.
            evidence_records: Mapping of parameter_key -> {
                "evidence_id": str,
                "evidence_version_id": str,
                "trust_tier": int,
                "verification_state": str,
                "has_conflict": bool,
            }
        """
        config_hash = compute_configuration_hash(model_config)
        param_outcomes: list[ParameterEvaluationOutcome] = []
        limitations_summary: dict[str, Any] = {"parameter_limitations": []}

        # 1. Evaluate individual parameters
        for p in model_config.parameters:
            outcome = cls._evaluate_parameter(
                param=p,
                attribute_values=attribute_values,
                evidence_info=evidence_records.get(p.key),
            )
            param_outcomes.append(outcome)
            if outcome.limitations:
                limitations_summary["parameter_limitations"].append({
                    "parameter_key": p.key,
                    "reasons": outcome.limitations,
                })

        # 2. Weight Normalization & Aggregation
        total_configured_weight: Decimal = sum((p.weight for p in model_config.parameters), Decimal("0.0"))
        evaluated_outcomes = [o for o in param_outcomes if o.status == "evaluated" and o.score is not None]
        eligible_weight: Decimal = sum((o.weight for o in evaluated_outcomes), Decimal("0.0"))

        # 3. Coverage Calculation
        if total_configured_weight > Decimal("0.0"):
            coverage_ratio = (eligible_weight / total_configured_weight).quantize(
                Decimal("0.001"), rounding=ROUND_HALF_UP
            )
        else:
            coverage_ratio = Decimal("0.000")

        is_coverage_sufficient = coverage_ratio >= model_config.coverage_policy.coverage_floor
        coverage_state = "sufficient" if is_coverage_sufficient else "insufficient"

        if not is_coverage_sufficient:
            limitations_summary["coverage"] = (
                f"Evaluated coverage ({float(coverage_ratio)*100:.1f}%) is below the required "
                f"floor of {float(model_config.coverage_policy.coverage_floor)*100:.1f}%."
            )

        # 4. Score Aggregation
        overall_score: Decimal | None = None
        if is_coverage_sufficient and eligible_weight > Decimal("0.0"):
            weighted_sum = Decimal("0.0")
            for o in evaluated_outcomes:
                assert o.score is not None
                norm_weight = (o.weight / eligible_weight).quantize(Decimal("0.00001"), rounding=ROUND_HALF_UP)
                o.effective_weight = norm_weight
                contrib = (o.score * norm_weight).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
                o.contribution = contrib
                weighted_sum += o.score * (o.weight / eligible_weight)

            # Round to aggregation precision
            prec_str = "0." + "0" * model_config.aggregation.precision if model_config.aggregation.precision > 0 else "1"
            overall_score = max(
                Decimal("0.0"),
                min(Decimal("100.0"), weighted_sum.quantize(Decimal(prec_str), rounding=ROUND_HALF_UP)),
            )
        else:
            # When coverage is insufficient or no parameters evaluated, overall_score remains strictly None
            for o in evaluated_outcomes:
                o.effective_weight = Decimal("0.0")
                o.contribution = None

        # 5. Deterministic Confidence Calculation
        confidence_score, confidence_state = cls._calculate_confidence(
            model_config=model_config,
            param_outcomes=param_outcomes,
            total_configured_weight=total_configured_weight,
            limitations_summary=limitations_summary,
        )

        # 6. Compute Cryptographic Input & Output Fingerprints
        input_fp = cls._compute_input_fingerprint(attribute_values, evidence_records)
        output_fp = cls._compute_output_fingerprint(
            overall_score=overall_score,
            coverage=coverage_ratio,
            confidence_score=confidence_score,
            param_outcomes=param_outcomes,
        )

        return EvaluationCalculationOutcome(
            overall_score=overall_score,
            coverage=coverage_ratio,
            coverage_state=coverage_state,
            confidence_score=confidence_score,
            confidence_state=confidence_state,
            limitations=limitations_summary,
            parameter_results=param_outcomes,
            configuration_hash=config_hash,
            input_fingerprint=input_fp,
            output_fingerprint=output_fp,
        )

    @classmethod
    def _evaluate_parameter(
        cls,
        param: ParameterConfig,
        attribute_values: dict[str, Any],
        evidence_info: dict[str, Any] | None,
    ) -> ParameterEvaluationOutcome:
        """Evaluate a single parameter against attribute value and evidence eligibility policy."""
        val = attribute_values.get(param.attribute_key)
        if val is None:
            val = attribute_values.get(param.key)

        ev_id = str(evidence_info["evidence_id"]) if evidence_info and evidence_info.get("evidence_id") else None
        ev_ver_id = (
            str(evidence_info["evidence_version_id"])
            if evidence_info and evidence_info.get("evidence_version_id")
            else None
        )
        trust_tier = evidence_info.get("trust_tier") if evidence_info else None
        ver_state = evidence_info.get("verification_state", "unverified") if evidence_info else None
        has_conflict = bool(evidence_info.get("has_conflict", False)) if evidence_info else False

        evidence_ids = [ev_id] if ev_id else []
        evidence_version_ids = [ev_ver_id] if ev_ver_id else []
        limitations: list[str] = []

        # Check for missing data
        if val is None:
            return ParameterEvaluationOutcome(
                parameter_key=param.key,
                attribute_key=param.attribute_key,
                label=param.label,
                weight=param.weight,
                effective_weight=Decimal("0.0"),
                score=None,
                status="missing",
                scoring_rule=param.scoring_rule,
                raw_input_value=None,
                normalized_value=None,
                contribution=None,
                is_critical=param.is_critical,
                evidence_ids=evidence_ids,
                evidence_version_ids=evidence_version_ids,
                limitations=["Parameter attribute value is missing in catalog and extraction."],
                explanation=f"Missing specification for '{param.label}'. Value cannot be scored.",
            )

        # Check for conflicting evidence
        if has_conflict or ver_state == "conflicting":
            limitations.append("Contradictory evidence values detected across sources; score withheld pending resolution.")
            return ParameterEvaluationOutcome(
                parameter_key=param.key,
                attribute_key=param.attribute_key,
                label=param.label,
                weight=param.weight,
                effective_weight=Decimal("0.0"),
                score=None,
                status="conflicting",
                scoring_rule=param.scoring_rule,
                raw_input_value=val,
                normalized_value=val,
                contribution=None,
                is_critical=param.is_critical,
                evidence_ids=evidence_ids,
                evidence_version_ids=evidence_version_ids,
                limitations=limitations,
                explanation=f"Conflicting evidence found for '{param.label}'.",
                trust_tier=trust_tier,
                verification_state=ver_state,
            )

        # Check evidence eligibility policy
        if (
            evidence_info
            and trust_tier is not None
            and trust_tier not in param.evidence_policy.allowed_trust_tiers
        ):
            limitations.append(
                f"Evidence trust tier T{trust_tier} not eligible under model policy (allowed: {param.evidence_policy.allowed_trust_tiers})."
            )
            return ParameterEvaluationOutcome(
                parameter_key=param.key,
                attribute_key=param.attribute_key,
                label=param.label,
                weight=param.weight,
                effective_weight=Decimal("0.0"),
                score=None,
                status="unverified",
                scoring_rule=param.scoring_rule,
                raw_input_value=val,
                normalized_value=val,
                contribution=None,
                is_critical=param.is_critical,
                evidence_ids=evidence_ids,
                evidence_version_ids=evidence_version_ids,
                limitations=limitations,
                explanation=f"Evidence for '{param.label}' does not meet trust tier eligibility.",
                trust_tier=trust_tier,
                verification_state=ver_state,
            )

        # Execute pure scoring rule
        try:
            if param.scoring_rule == "linear_range":
                p_params = LinearRangeRuleParams.model_validate(param.rule_params)
                score = evaluate_linear_range(val, p_params)
                explanation = f"Linear range evaluation ({p_params.min_val} to {p_params.max_val}) mapped value {val} to score {score}."
            elif param.scoring_rule == "piecewise":
                pw_params = PiecewiseRuleParams.model_validate(param.rule_params)
                score = evaluate_piecewise(val, pw_params)
                explanation = f"Piecewise evaluation mapped value {val} to score {score} across {len(pw_params.breakpoints)} breakpoints."
            elif param.scoring_rule == "boolean":
                b_params = BooleanRuleParams.model_validate(param.rule_params)
                score = evaluate_boolean(val, b_params)
                explanation = f"Boolean evaluation mapped value {val} to score {score}."
            elif param.scoring_rule == "ordinal":
                o_params = OrdinalRuleParams.model_validate(param.rule_params)
                score = evaluate_ordinal(val, o_params)
                explanation = f"Ordinal evaluation mapped category '{val}' to score {score}."
            else:
                raise ValueError(f"Unsupported scoring rule: {param.scoring_rule}")

            return ParameterEvaluationOutcome(
                parameter_key=param.key,
                attribute_key=param.attribute_key,
                label=param.label,
                weight=param.weight,
                effective_weight=Decimal("0.0"),  # populated during normalization
                score=score,
                status="evaluated",
                scoring_rule=param.scoring_rule,
                raw_input_value=val,
                normalized_value=val,
                contribution=None,  # populated during normalization
                is_critical=param.is_critical,
                evidence_ids=evidence_ids,
                evidence_version_ids=evidence_version_ids,
                limitations=limitations,
                explanation=explanation,
                trust_tier=trust_tier,
                verification_state=ver_state,
            )

        except (ValueError, TypeError, ZeroDivisionError, ArithmeticError) as exc:
            limitations.append(f"Scoring error: {exc}")
            return ParameterEvaluationOutcome(
                parameter_key=param.key,
                attribute_key=param.attribute_key,
                label=param.label,
                weight=param.weight,
                effective_weight=Decimal("0.0"),
                score=None,
                status="invalid",
                scoring_rule=param.scoring_rule,
                raw_input_value=val,
                normalized_value=val,
                contribution=None,
                is_critical=param.is_critical,
                evidence_ids=evidence_ids,
                evidence_version_ids=evidence_version_ids,
                limitations=limitations,
                explanation=f"Error evaluating '{param.label}': {exc}",
                trust_tier=trust_tier,
                verification_state=ver_state,
            )

    @classmethod
    def _calculate_confidence(
        cls,
        model_config: EvaluationModelConfig,
        param_outcomes: list[ParameterEvaluationOutcome],
        total_configured_weight: Decimal,
        limitations_summary: dict[str, Any],
    ) -> tuple[Decimal, str]:
        """Compute evidence-aware deterministic confidence score and confidence state."""
        if total_configured_weight <= Decimal("0.0"):
            return Decimal("0.000"), "insufficient_evidence"

        tier_weights = {1: Decimal("1.00"), 2: Decimal("0.85"), 3: Decimal("0.60"), 4: Decimal("0.30")}
        ver_weights = {"verified": Decimal("1.00"), "unverified": Decimal("0.70"), "conflicting": Decimal("0.00")}

        weighted_confidence_sum = Decimal("0.0")
        has_any_conflict = False

        for o in param_outcomes:
            if o.status == "evaluated" and o.trust_tier is not None:
                t_score = tier_weights.get(o.trust_tier, Decimal("0.30"))
                v_score = ver_weights.get(o.verification_state or "unverified", Decimal("0.70"))
                param_conf = t_score * v_score
                weighted_confidence_sum += param_conf * o.weight
            elif o.status == "conflicting":
                has_any_conflict = True

        raw_confidence = weighted_confidence_sum / total_configured_weight

        # Apply conflict penalty if contradictions exist
        if has_any_conflict:
            raw_confidence = max(Decimal("0.000"), raw_confidence - Decimal("0.150"))
            limitations_summary["conflicts"] = "Confidence penalized due to unresolved conflicting evidence."

        confidence = raw_confidence.quantize(Decimal("0.001"), rounding=ROUND_HALF_UP)

        # Categorize confidence state
        if confidence >= model_config.confidence_policy.high_threshold:
            state = "high"
        elif confidence >= model_config.confidence_policy.medium_threshold:
            state = "medium"
        elif confidence > Decimal("0.000"):
            state = "low"
        else:
            state = "insufficient_evidence"

        return confidence, state

    @classmethod
    def _compute_input_fingerprint(
        cls,
        attribute_values: dict[str, Any],
        evidence_records: dict[str, dict[str, Any]],
    ) -> str:
        """Generate deterministic SHA-256 digest of evaluation inputs and evidence snapshots."""
        canonical_inputs = {
            "attributes": {k: str(v) for k, v in sorted(attribute_values.items())},
            "evidence": {
                k: {
                    "evidence_id": str(v.get("evidence_id")),
                    "evidence_version_id": str(v.get("evidence_version_id")),
                    "trust_tier": v.get("trust_tier"),
                    "verification_state": v.get("verification_state"),
                }
                for k, v in sorted(evidence_records.items())
            },
        }
        raw_json = json.dumps(canonical_inputs, sort_keys=True, separators=(",", ":"))
        return hashlib.sha256(raw_json.encode("utf-8")).hexdigest()

    @classmethod
    def _compute_output_fingerprint(
        cls,
        overall_score: Decimal | None,
        coverage: Decimal,
        confidence_score: Decimal,
        param_outcomes: list[ParameterEvaluationOutcome],
    ) -> str:
        """Generate deterministic SHA-256 digest of evaluation outcomes."""
        canonical_outputs = {
            "overall_score": str(overall_score) if overall_score is not None else None,
            "coverage": str(coverage),
            "confidence_score": str(confidence_score),
            "parameters": [
                {
                    "key": o.parameter_key,
                    "score": str(o.score) if o.score is not None else None,
                    "status": o.status,
                    "effective_weight": str(o.effective_weight),
                    "contribution": str(o.contribution) if o.contribution is not None else None,
                }
                for o in sorted(param_outcomes, key=lambda x: x.parameter_key)
            ],
        }
        raw_json = json.dumps(canonical_outputs, sort_keys=True, separators=(",", ":"))
        return hashlib.sha256(raw_json.encode("utf-8")).hexdigest()
