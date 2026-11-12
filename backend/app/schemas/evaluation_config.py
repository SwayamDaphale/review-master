"""Pydantic v2 configuration schema for versioned, deterministic evaluation models."""

import hashlib
import json
import math
from decimal import Decimal
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


def _canonical_json(obj: Any) -> str:
    """Produce deterministic byte-stable JSON representation."""
    if isinstance(obj, Decimal):
        # Format Decimal consistently without trailing scientific notation
        return str(obj)
    if isinstance(obj, dict):
        return "{" + ",".join(f"{json.dumps(k)}:{_canonical_json(v)}" for k, v in sorted(obj.items())) + "}"
    if isinstance(obj, (list, tuple)):
        return "[" + ",".join(_canonical_json(item) for item in obj) + "]"
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def compute_configuration_hash(definition: dict[str, Any] | BaseModel) -> str:
    """Compute deterministic SHA-256 hash of canonical model definition."""
    if isinstance(definition, BaseModel):
        dumped = definition.model_dump(mode="json")
    else:
        dumped = definition
    canonical_repr = _canonical_json(dumped)
    return hashlib.sha256(canonical_repr.encode("utf-8")).hexdigest()


class EvidencePolicyConfig(BaseModel):
    """Policy governing evidence eligibility for parameter scoring."""

    model_config = ConfigDict(extra="forbid")

    allowed_trust_tiers: list[int] = Field(default_factory=lambda: [1, 2, 3])
    required_verification_states: list[str] = Field(
        default_factory=lambda: ["verified", "unverified"]
    )
    allow_unverified: bool = True
    allow_conflicting: bool = False


class AggregationConfig(BaseModel):
    """Scoring aggregation and normalization policy."""

    model_config = ConfigDict(extra="forbid")

    formula: Literal["weighted_average"] = "weighted_average"
    precision: int = Field(default=2, ge=0, le=4)


class CoveragePolicyConfig(BaseModel):
    """Policy defining coverage threshold and insufficiency criteria."""

    model_config = ConfigDict(extra="forbid")

    coverage_floor: Decimal = Field(default=Decimal("0.40"), ge=Decimal("0.0"), le=Decimal("1.0"))
    insufficient_coverage_action: Literal["withhold_score", "flag_limited"] = "withhold_score"


class ConfidencePolicyConfig(BaseModel):
    """Thresholds for categorizing deterministic confidence states."""

    model_config = ConfigDict(extra="forbid")

    high_threshold: Decimal = Field(default=Decimal("0.75"), ge=Decimal("0.0"), le=Decimal("1.0"))
    medium_threshold: Decimal = Field(default=Decimal("0.45"), ge=Decimal("0.0"), le=Decimal("1.0"))


class LinearRangeRuleParams(BaseModel):
    """Parameters for linear_range scoring rule."""

    model_config = ConfigDict(extra="forbid")

    min_val: Decimal
    max_val: Decimal
    direction: Literal["higher_is_better", "lower_is_better"] = "higher_is_better"
    clamp_out_of_bounds: bool = True

    @model_validator(mode="after")
    def validate_range(self) -> "LinearRangeRuleParams":
        if self.min_val >= self.max_val:
            raise ValueError(f"min_val ({self.min_val}) must be strictly less than max_val ({self.max_val})")
        return self


class PiecewiseBreakpoint(BaseModel):
    """Input-to-output point mapping for piecewise scoring rule."""

    model_config = ConfigDict(extra="forbid")

    x: Decimal
    score: Decimal = Field(ge=Decimal("0.0"), le=Decimal("100.0"))


class PiecewiseRuleParams(BaseModel):
    """Parameters for piecewise scoring rule with monotonic breakpoints."""

    model_config = ConfigDict(extra="forbid")

    breakpoints: list[PiecewiseBreakpoint] = Field(min_length=2)
    interpolate: bool = True

    @model_validator(mode="after")
    def validate_monotonic_x(self) -> "PiecewiseRuleParams":
        for i in range(len(self.breakpoints) - 1):
            if self.breakpoints[i].x >= self.breakpoints[i + 1].x:
                raise ValueError(
                    f"Breakpoints must be strictly increasing on x: "
                    f"{self.breakpoints[i].x} >= {self.breakpoints[i+1].x}"
                )
        return self


class BooleanRuleParams(BaseModel):
    """Parameters for boolean scoring rule."""

    model_config = ConfigDict(extra="forbid")

    true_score: Decimal = Field(default=Decimal("100.0"), ge=Decimal("0.0"), le=Decimal("100.0"))
    false_score: Decimal = Field(default=Decimal("0.0"), ge=Decimal("0.0"), le=Decimal("100.0"))


class OrdinalRuleParams(BaseModel):
    """Parameters for ordinal category score mapping."""

    model_config = ConfigDict(extra="forbid")

    mapping: dict[str, Decimal] = Field(min_length=1)

    @field_validator("mapping")
    @classmethod
    def validate_scores(cls, v: dict[str, Decimal]) -> dict[str, Decimal]:
        normalized: dict[str, Decimal] = {}
        for k, score in v.items():
            if score < Decimal("0.0") or score > Decimal("100.0"):
                raise ValueError(f"Ordinal score for '{k}' must be between 0 and 100, got {score}")
            normalized[k.strip().lower()] = score
        return normalized


class ParameterConfig(BaseModel):
    """Definition and scoring configuration for a single evaluation parameter."""

    model_config = ConfigDict(extra="forbid")

    key: str = Field(min_length=1, max_length=64)
    attribute_key: str = Field(min_length=1, max_length=64)
    label: str = Field(min_length=1, max_length=128)
    weight: Decimal = Field(gt=Decimal("0.0"), description="Configured non-negative parameter weight")
    scoring_rule: Literal["linear_range", "piecewise", "boolean", "ordinal"]
    rule_params: dict[str, Any]
    is_critical: bool = False
    is_required: bool = False
    evidence_policy: EvidencePolicyConfig = Field(default_factory=EvidencePolicyConfig)

    @field_validator("rule_params", mode="before")
    @classmethod
    def convert_rule_params_to_dict(cls, v: Any) -> Any:
        if isinstance(v, BaseModel):
            return v.model_dump()
        return v

    @field_validator("weight")
    @classmethod
    def validate_weight_finite(cls, v: Decimal) -> Decimal:
        if not math.isfinite(float(v)) or v <= Decimal("0.0"):
            raise ValueError(f"Weight must be finite and strictly positive, got {v}")
        return v

    @model_validator(mode="after")
    def validate_rule_parameters(self) -> "ParameterConfig":
        """Strictly validate rule_params against the specified scoring_rule."""
        try:
            if self.scoring_rule == "linear_range":
                LinearRangeRuleParams.model_validate(self.rule_params)
            elif self.scoring_rule == "piecewise":
                PiecewiseRuleParams.model_validate(self.rule_params)
            elif self.scoring_rule == "boolean":
                BooleanRuleParams.model_validate(self.rule_params)
            elif self.scoring_rule == "ordinal":
                OrdinalRuleParams.model_validate(self.rule_params)
        except Exception as exc:
            raise ValueError(f"Invalid rule_params for scoring_rule '{self.scoring_rule}': {exc}") from exc
        return self


class EvaluationModelConfig(BaseModel):
    """Complete versioned evaluation model configuration contract."""

    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=1, max_length=128)
    version: str = Field(pattern=r"^\d+\.\d+\.\d+$")
    category_key: str = Field(min_length=1, max_length=64)
    description: str | None = None
    parameters: list[ParameterConfig] = Field(min_length=1)
    aggregation: AggregationConfig = Field(default_factory=AggregationConfig)
    coverage_policy: CoveragePolicyConfig = Field(default_factory=CoveragePolicyConfig)
    confidence_policy: ConfidencePolicyConfig = Field(default_factory=ConfidencePolicyConfig)

    @model_validator(mode="after")
    def validate_model_integrity(self) -> "EvaluationModelConfig":
        # 1. Reject duplicate parameter keys
        keys = [p.key for p in self.parameters]
        if len(keys) != len(set(keys)):
            duplicates = [k for k in keys if keys.count(k) > 1]
            raise ValueError(f"Duplicate parameter keys found: {set(duplicates)}")

        # 2. Total configured weight must be positive
        total_weight = sum(p.weight for p in self.parameters)
        if total_weight <= Decimal("0.0"):
            raise ValueError("Total configured weight of all parameters must be strictly greater than 0")

        return self
