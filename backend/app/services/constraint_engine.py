"""Deterministic hard constraint evaluation engine implementing three-valued logic.

Outcomes:
- PASS: Candidate has verified attribute value that satisfies constraint.
- FAIL: Candidate has known value that violates constraint.
- UNKNOWN: Candidate attribute is missing, null, unverified, or ambiguous.

Critical rule:
Both FAIL and UNKNOWN render candidate product INELIGIBLE for strict recommendation.
"""

from decimal import Decimal
from typing import Any

from app.schemas.recommendation import (
    CandidateEvaluationOutcome,
    ConstraintEvaluationDetail,
    ConstraintOutcome,
    HardConstraint,
    ParsedRequirements,
)


def _to_float(val: Any) -> float | None:
    if val is None:
        return None
    if isinstance(val, (int, float)):
        return float(val)
    if isinstance(val, Decimal):
        return float(val)
    if isinstance(val, str):
        try:
            return float(val.strip().replace(",", ""))
        except ValueError:
            return None
    return None


class ConstraintEngine:
    """Deterministic constraint validator executing three-valued logic."""

    @classmethod
    def evaluate_candidate(
        cls,
        *,
        requirements: ParsedRequirements,
        variant_id: Any,
        product_id: Any,
        product_name: str,
        manufacturer: str,
        sku_label: str,
        attribute_values: dict[str, Any],
        current_price: float | None = None,
        price_available: bool = False,
    ) -> CandidateEvaluationOutcome:
        """Evaluate all hard constraints against a candidate product variant."""
        constraint_details: list[ConstraintEvaluationDetail] = []
        exclusion_reasons: list[str] = []

        # 1. Evaluate Brand Exclusions
        if requirements.excluded_brands:
            mfr_lower = manufacturer.lower().strip()
            for excluded in requirements.excluded_brands:
                if excluded.lower().strip() in mfr_lower:
                    detail = ConstraintEvaluationDetail(
                        attribute_key="brand",
                        operator="!=",
                        target_value=excluded,
                        actual_value=manufacturer,
                        outcome=ConstraintOutcome.FAIL,
                        reason=f"Brand '{manufacturer}' matches excluded brand '{excluded}'.",
                    )
                    constraint_details.append(detail)
                    exclusion_reasons.append(detail.reason)

        # 2. Evaluate Maximum Budget Constraint
        if requirements.budget_max is not None:
            if not price_available or current_price is None:
                detail = ConstraintEvaluationDetail(
                    attribute_key="price",
                    operator="<=",
                    target_value=requirements.budget_max,
                    actual_value=None,
                    unit=requirements.budget_currency,
                    outcome=ConstraintOutcome.UNKNOWN,
                    reason=f"Current price is unavailable; cannot verify budget under ₹{requirements.budget_max:,.0f}.",
                )
                constraint_details.append(detail)
                exclusion_reasons.append(detail.reason)
            else:
                if current_price <= requirements.budget_max:
                    detail = ConstraintEvaluationDetail(
                        attribute_key="price",
                        operator="<=",
                        target_value=requirements.budget_max,
                        actual_value=current_price,
                        unit=requirements.budget_currency,
                        outcome=ConstraintOutcome.PASS,
                        reason=f"Price ₹{current_price:,.0f} satisfies budget limit of ₹{requirements.budget_max:,.0f}.",
                    )
                    constraint_details.append(detail)
                else:
                    detail = ConstraintEvaluationDetail(
                        attribute_key="price",
                        operator="<=",
                        target_value=requirements.budget_max,
                        actual_value=current_price,
                        unit=requirements.budget_currency,
                        outcome=ConstraintOutcome.FAIL,
                        reason=f"Price ₹{current_price:,.0f} exceeds maximum budget of ₹{requirements.budget_max:,.0f}.",
                    )
                    constraint_details.append(detail)
                    exclusion_reasons.append(detail.reason)

        # 3. Evaluate Attribute Hard Constraints
        for hc in requirements.hard_constraints:
            detail = cls._evaluate_single_constraint(hc, attribute_values)
            constraint_details.append(detail)
            if detail.outcome != ConstraintOutcome.PASS:
                exclusion_reasons.append(detail.reason)

        # 4. Determine Strict Eligibility: ALL must be PASS
        is_eligible = all(c.outcome == ConstraintOutcome.PASS for c in constraint_details)

        return CandidateEvaluationOutcome(
            variant_id=variant_id,
            product_id=product_id,
            product_name=product_name,
            sku_label=sku_label,
            is_eligible=is_eligible,
            constraints=constraint_details,
            exclusion_reasons=exclusion_reasons,
        )

    @classmethod
    def _evaluate_single_constraint(
        cls,
        hc: HardConstraint,
        attribute_values: dict[str, Any],
    ) -> ConstraintEvaluationDetail:
        """Evaluate single attribute hard constraint with PASS/FAIL/UNKNOWN logic."""
        actual_val = attribute_values.get(hc.attribute_key)

        # UNKNOWN if attribute value is missing or null
        if actual_val is None:
            return ConstraintEvaluationDetail(
                attribute_key=hc.attribute_key,
                operator=hc.operator,
                target_value=hc.target_value,
                actual_value=None,
                unit=hc.unit,
                outcome=ConstraintOutcome.UNKNOWN,
                reason=f"Required attribute '{hc.attribute_key}' is not available in catalog specifications.",
            )

        op = hc.operator.strip()
        num_target = _to_float(hc.target_value)
        num_actual = _to_float(actual_val)

        # Numeric comparisons
        if num_target is not None and num_actual is not None:
            passed = False
            if op in (">=", "gte"):
                passed = num_actual >= num_target
            elif op in (">", "gt"):
                passed = num_actual > num_target
            elif op in ("<=", "lte"):
                passed = num_actual <= num_target
            elif op in ("<", "lt"):
                passed = num_actual < num_target
            elif op in ("==", "=", "eq"):
                passed = num_actual == num_target
            elif op in ("!=", "ne"):
                passed = num_actual != num_target
            else:
                passed = num_actual >= num_target

            if passed:
                return ConstraintEvaluationDetail(
                    attribute_key=hc.attribute_key,
                    operator=op,
                    target_value=hc.target_value,
                    actual_value=num_actual,
                    unit=hc.unit,
                    outcome=ConstraintOutcome.PASS,
                    reason=f"{hc.attribute_key.upper()} of {num_actual} {hc.unit or ''} satisfies constraint {op} {hc.target_value}.",
                )
            else:
                return ConstraintEvaluationDetail(
                    attribute_key=hc.attribute_key,
                    operator=op,
                    target_value=hc.target_value,
                    actual_value=num_actual,
                    unit=hc.unit,
                    outcome=ConstraintOutcome.FAIL,
                    reason=f"{hc.attribute_key.upper()} of {num_actual} {hc.unit or ''} violates constraint {op} {hc.target_value}.",
                )

        # Boolean comparisons
        if isinstance(hc.target_value, bool) or str(hc.target_value).lower() in ("true", "false"):
            target_bool = bool(hc.target_value) if isinstance(hc.target_value, bool) else str(hc.target_value).lower() == "true"
            actual_bool = bool(actual_val) if isinstance(actual_val, bool) else str(actual_val).lower() == "true"
            if op in ("==", "=", "eq"):
                passed = target_bool == actual_bool
            elif op in ("!=", "ne"):
                passed = target_bool != actual_bool
            else:
                passed = target_bool == actual_bool

            if passed:
                return ConstraintEvaluationDetail(
                    attribute_key=hc.attribute_key,
                    operator=op,
                    target_value=target_bool,
                    actual_value=actual_bool,
                    unit=hc.unit,
                    outcome=ConstraintOutcome.PASS,
                    reason=f"{hc.attribute_key.upper()} boolean state matches requirement.",
                )
            else:
                return ConstraintEvaluationDetail(
                    attribute_key=hc.attribute_key,
                    operator=op,
                    target_value=target_bool,
                    actual_value=actual_bool,
                    unit=hc.unit,
                    outcome=ConstraintOutcome.FAIL,
                    reason=f"{hc.attribute_key.upper()} boolean state does not match requirement.",
                )

        # String set/in comparisons
        if op == "in" and isinstance(hc.target_value, (list, set, tuple)):
            passed = str(actual_val).lower() in [str(x).lower() for x in hc.target_value]
            outcome = ConstraintOutcome.PASS if passed else ConstraintOutcome.FAIL
            return ConstraintEvaluationDetail(
                attribute_key=hc.attribute_key,
                operator=op,
                target_value=hc.target_value,
                actual_value=actual_val,
                unit=hc.unit,
                outcome=outcome,
                reason=f"Value '{actual_val}' {'matches' if passed else 'not in'} allowed choices.",
            )

        # Generic string comparison
        if op in ("==", "=", "eq"):
            passed = str(actual_val).lower() == str(hc.target_value).lower()
            outcome = ConstraintOutcome.PASS if passed else ConstraintOutcome.FAIL
            return ConstraintEvaluationDetail(
                attribute_key=hc.attribute_key,
                operator=op,
                target_value=hc.target_value,
                actual_value=actual_val,
                unit=hc.unit,
                outcome=outcome,
                reason=f"{hc.attribute_key} '{actual_val}' {'matches' if passed else 'does not match'} required value '{hc.target_value}'.",
            )

        # Default fallback to UNKNOWN if types unsupported
        return ConstraintEvaluationDetail(
            attribute_key=hc.attribute_key,
            operator=op,
            target_value=hc.target_value,
            actual_value=actual_val,
            unit=hc.unit,
            outcome=ConstraintOutcome.UNKNOWN,
            reason=f"Incompatible types or operator '{op}' for attribute '{hc.attribute_key}'.",
        )

