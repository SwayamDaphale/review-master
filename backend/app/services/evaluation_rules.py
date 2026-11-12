"""Deterministic scoring rule engine conforming to ADR-0003 and Phase B9 specs.

Pure, non-LLM, mathematical scoring rules operating on Decimal arithmetic:
- Linear Range (higher-is-better, lower-is-better)
- Piecewise (ordered monotonic breakpoints with linear interpolation)
- Boolean (distinct true/false mappings; missing is never false)
- Ordinal (strictly mapped category scores; no guessing)
"""

from decimal import ROUND_HALF_UP, Decimal
from typing import Any

from app.schemas.evaluation_config import (
    BooleanRuleParams,
    LinearRangeRuleParams,
    OrdinalRuleParams,
    PiecewiseRuleParams,
)

CALC_PRECISION = Decimal("0.0001")


def _to_decimal(val: Any) -> Decimal:
    """Convert numeric input to Decimal without floating point corruption."""
    if isinstance(val, Decimal):
        return val
    if isinstance(val, (int, str)):
        return Decimal(str(val))
    if isinstance(val, float):
        return Decimal(str(round(val, 6)))
    raise ValueError(f"Cannot convert value {val} of type {type(val)} to Decimal")


def evaluate_linear_range(
    val: Any,
    params: LinearRangeRuleParams,
) -> Decimal:
    """Compute score for linear_range rule mapped to [0, 100]."""
    dec_val = _to_decimal(val)
    min_val = params.min_val
    max_val = params.max_val
    span = max_val - min_val

    if span <= Decimal(0):
        raise ValueError(f"Invalid range span: min ({min_val}) >= max ({max_val})")

    if dec_val <= min_val:
        score = Decimal("0.0") if params.direction == "higher_is_better" else Decimal("100.0")
    elif dec_val >= max_val:
        score = Decimal("100.0") if params.direction == "higher_is_better" else Decimal("0.0")
    else:
        fraction = (dec_val - min_val) / span
        if params.direction == "higher_is_better":
            score = fraction * Decimal("100.0")
        else:
            score = (Decimal("1.0") - fraction) * Decimal("100.0")

    # Clamp and round
    score = max(Decimal("0.0"), min(Decimal("100.0"), score))
    return score.quantize(CALC_PRECISION, rounding=ROUND_HALF_UP)


def evaluate_piecewise(
    val: Any,
    params: PiecewiseRuleParams,
) -> Decimal:
    """Compute score for piecewise rule using ordered monotonic breakpoints."""
    dec_val = _to_decimal(val)
    pts = params.breakpoints

    # Below first breakpoint
    if dec_val <= pts[0].x:
        return pts[0].score.quantize(CALC_PRECISION, rounding=ROUND_HALF_UP)

    # Above last breakpoint
    if dec_val >= pts[-1].x:
        return pts[-1].score.quantize(CALC_PRECISION, rounding=ROUND_HALF_UP)

    # Find segment [p1, p2]
    for i in range(len(pts) - 1):
        p1 = pts[i]
        p2 = pts[i + 1]
        if p1.x <= dec_val <= p2.x:
            if not params.interpolate or p1.x == p2.x:
                return p1.score.quantize(CALC_PRECISION, rounding=ROUND_HALF_UP)
            fraction = (dec_val - p1.x) / (p2.x - p1.x)
            score = p1.score + fraction * (p2.score - p1.score)
            score = max(Decimal("0.0"), min(Decimal("100.0"), score))
            return score.quantize(CALC_PRECISION, rounding=ROUND_HALF_UP)

    return pts[-1].score.quantize(CALC_PRECISION, rounding=ROUND_HALF_UP)


def evaluate_boolean(
    val: Any,
    params: BooleanRuleParams,
) -> Decimal:
    """Compute score for boolean rule. Missing must remain missing and cannot enter here."""
    if val is None:
        raise ValueError("Missing value cannot be evaluated as boolean")
    if isinstance(val, bool):
        b_val = val
    elif isinstance(val, str):
        v_low = val.strip().lower()
        if v_low in ("true", "1", "yes"):
            b_val = True
        elif v_low in ("false", "0", "no"):
            b_val = False
        else:
            raise ValueError(f"Cannot parse string '{val}' as boolean")
    else:
        b_val = bool(val)

    score = params.true_score if b_val else params.false_score
    return score.quantize(CALC_PRECISION, rounding=ROUND_HALF_UP)


def evaluate_ordinal(
    val: Any,
    params: OrdinalRuleParams,
) -> Decimal:
    """Compute score for ordinal category mapping. Unknown categories are rejected."""
    if val is None:
        raise ValueError("Missing value cannot be evaluated as ordinal")
    key = str(val).strip().lower()
    if key not in params.mapping:
        raise KeyError(f"Unknown ordinal category '{val}'. Valid options: {list(params.mapping.keys())}")
    score = params.mapping[key]
    return score.quantize(CALC_PRECISION, rounding=ROUND_HALF_UP)
