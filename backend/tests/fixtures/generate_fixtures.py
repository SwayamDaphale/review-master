"""Script to generate the 14 required golden fixtures for Phase B9 evaluation determinism gate."""

import json
from decimal import Decimal
from pathlib import Path
from typing import Any

from app.schemas.evaluation_config import EvaluationModelConfig
from app.services.evaluation_calculator import DeterministicEvaluationCalculator

FIXTURES_DIR = Path(__file__).resolve().parent / "evaluations"
FIXTURES_DIR.mkdir(parents=True, exist_ok=True)


def _base_model_config() -> dict[str, Any]:
    return {
        "name": "Smartphone Quality Index",
        "version": "1.0.0",
        "category_key": "smartphone",
        "description": "Deterministic scoring model for smartphones",
        "parameters": [
            {
                "key": "battery_capacity_mah",
                "attribute_key": "battery_capacity_mah",
                "label": "Battery Capacity",
                "weight": "0.30",
                "scoring_rule": "linear_range",
                "rule_params": {
                    "min_val": "3000",
                    "max_val": "6000",
                    "direction": "higher_is_better",
                    "clamp_out_of_bounds": True,
                },
                "is_critical": True,
                "is_required": True,
            },
            {
                "key": "ram_gb",
                "attribute_key": "ram_gb",
                "label": "System RAM",
                "weight": "0.25",
                "scoring_rule": "piecewise",
                "rule_params": {
                    "breakpoints": [
                        {"x": "4", "score": "20.0"},
                        {"x": "8", "score": "60.0"},
                        {"x": "12", "score": "90.0"},
                        {"x": "16", "score": "100.0"},
                    ],
                    "interpolate": True,
                },
                "is_critical": False,
                "is_required": True,
            },
            {
                "key": "supports_5g",
                "attribute_key": "supports_5g",
                "label": "5G Connectivity",
                "weight": "0.20",
                "scoring_rule": "boolean",
                "rule_params": {
                    "true_score": "100.0",
                    "false_score": "0.0",
                },
                "is_critical": False,
                "is_required": False,
            },
            {
                "key": "display_type",
                "attribute_key": "display_type",
                "label": "Display Panel Technology",
                "weight": "0.25",
                "scoring_rule": "ordinal",
                "rule_params": {
                    "mapping": {
                        "tft": "20.0",
                        "ips_lcd": "50.0",
                        "oled": "85.0",
                        "dynamic_amoled_2x": "100.0",
                    }
                },
                "is_critical": False,
                "is_required": False,
            },
        ],
        "aggregation": {"formula": "weighted_average", "precision": 2},
        "coverage_policy": {"coverage_floor": "0.40", "insufficient_coverage_action": "withhold_score"},
        "confidence_policy": {"high_threshold": "0.75", "medium_threshold": "0.45"},
    }


def generate_all():
    # 1. Linear range
    cfg1 = _base_model_config()
    attrs1 = {"battery_capacity_mah": 4500, "ram_gb": 8, "supports_5g": True, "display_type": "oled"}
    ev1 = {
        "battery_capacity_mah": {"evidence_id": "ev-01", "evidence_version_id": "ev-v-01", "trust_tier": 1, "verification_state": "verified"},
        "ram_gb": {"evidence_id": "ev-02", "evidence_version_id": "ev-v-02", "trust_tier": 2, "verification_state": "verified"},
        "supports_5g": {"evidence_id": "ev-03", "evidence_version_id": "ev-v-03", "trust_tier": 2, "verification_state": "verified"},
        "display_type": {"evidence_id": "ev-04", "evidence_version_id": "ev-v-04", "trust_tier": 2, "verification_state": "verified"},
    }
    _save_fixture("01_linear_range", "Linear range scoring", cfg1, attrs1, ev1)

    # 2. Piecewise
    attrs2 = {"battery_capacity_mah": 5000, "ram_gb": 10, "supports_5g": True, "display_type": "oled"}
    _save_fixture("02_piecewise", "Piecewise interpolation", cfg1, attrs2, ev1)

    # 3. Boolean True
    attrs3 = {"battery_capacity_mah": 5000, "ram_gb": 12, "supports_5g": True, "display_type": "dynamic_amoled_2x"}
    _save_fixture("03_boolean_true", "Boolean true mapping", cfg1, attrs3, ev1)

    # 4. Boolean False
    attrs4 = {"battery_capacity_mah": 5000, "ram_gb": 12, "supports_5g": False, "display_type": "dynamic_amoled_2x"}
    _save_fixture("04_boolean_false", "Boolean false distinct from missing", cfg1, attrs4, ev1)

    # 5. Ordinal
    attrs5 = {"battery_capacity_mah": 3000, "ram_gb": 4, "supports_5g": False, "display_type": "tft"}
    _save_fixture("05_ordinal", "Ordinal category scoring", cfg1, attrs5, ev1)

    # 6. Missing attributes (supports_5g and display_type missing)
    attrs6 = {"battery_capacity_mah": 5000, "ram_gb": 12}
    ev6 = {
        "battery_capacity_mah": ev1["battery_capacity_mah"],
        "ram_gb": ev1["ram_gb"],
    }
    _save_fixture("06_missing_attributes", "Missing attributes remain missing with reduced coverage", cfg1, attrs6, ev6)

    # 7. Conflicting attributes
    attrs7 = dict(attrs1)
    ev7 = dict(ev1)
    ev7["battery_capacity_mah"] = {"evidence_id": "ev-01", "evidence_version_id": "ev-v-01", "trust_tier": 2, "verification_state": "conflicting", "has_conflict": True}
    _save_fixture("07_conflicting_attributes", "Conflicting evidence score withheld and penalized", cfg1, attrs7, ev7)

    # 8. Insufficient coverage (only battery evaluated = 0.30 weight < 0.40 floor)
    attrs8 = {"battery_capacity_mah": 5000}
    ev8 = {"battery_capacity_mah": ev1["battery_capacity_mah"]}
    _save_fixture("08_insufficient_coverage", "Coverage below 0.40 floor withholds score", cfg1, attrs8, ev8)

    # 9. High confidence (all T1 verified)
    attrs9 = dict(attrs1)
    ev9 = {k: {"evidence_id": f"ev-{i}", "evidence_version_id": f"ev-v-{i}", "trust_tier": 1, "verification_state": "verified"} for i, k in enumerate(attrs9.keys(), 1)}
    _save_fixture("09_high_confidence", "High confidence from T1 verified evidence", cfg1, attrs9, ev9)

    # 10. Low confidence (all T4 unverified)
    attrs10 = dict(attrs1)
    ev10 = {k: {"evidence_id": f"ev-{i}", "evidence_version_id": f"ev-v-{i}", "trust_tier": 4, "verification_state": "unverified"} for i, k in enumerate(attrs10.keys(), 1)}
    _save_fixture("10_low_confidence", "Low confidence from unverified T4 evidence", cfg1, attrs10, ev10)

    # 11. Model version diff (v2.0.0 with different weights)
    cfg11 = _base_model_config()
    cfg11["version"] = "2.0.0"
    cfg11["parameters"][0]["weight"] = "0.50"
    cfg11["parameters"][1]["weight"] = "0.50"
    cfg11["parameters"] = cfg11["parameters"][:2]
    _save_fixture("11_model_version_diff", "Model version v2 with different parameter weights", cfg11, attrs1, ev1)

    # 12. Evidence version diff (different evidence version id changes input fingerprint)
    attrs12 = dict(attrs1)
    ev12 = dict(ev1)
    ev12["battery_capacity_mah"] = {"evidence_id": "ev-01", "evidence_version_id": "ev-v-99-new", "trust_tier": 1, "verification_state": "verified"}
    _save_fixture("12_evidence_version_diff", "Evidence version updated changes input fingerprint", cfg1, attrs12, ev12)

    # 13. Invalid configuration
    invalid_cfg = _base_model_config()
    invalid_cfg["parameters"][0]["weight"] = "-0.10"
    payload13 = {
        "name": "13_invalid_configuration",
        "description": "Invalid configuration with negative weight",
        "model_config": invalid_cfg,
        "variant_attributes": attrs1,
        "evidence_records": ev1,
        "is_valid": False,
        "expected_error": "Weight must be finite and non-negative",
    }
    with open(FIXTURES_DIR / "13_invalid_configuration.json", "w") as f:
        json.dump(payload13, f, indent=2)

    # 14. Variant hardware diff (RAM 16GB vs RAM 8GB)
    attrs14 = {"battery_capacity_mah": 5000, "ram_gb": 16, "supports_5g": True, "display_type": "dynamic_amoled_2x"}
    _save_fixture("14_variant_hardware_diff", "Hardware configuration variant diff", cfg1, attrs14, ev1)


def _save_fixture(name: str, desc: str, cfg_dict: dict[str, Any], attrs: dict[str, Any], ev_records: dict[str, Any]):
    model_cfg = EvaluationModelConfig.model_validate(cfg_dict)
    outcome = DeterministicEvaluationCalculator.calculate(
        model_config=model_cfg,
        attribute_values=attrs,
        evidence_records=ev_records,
    )
    expected_out = {
        "overall_score": str(outcome.overall_score) if outcome.overall_score is not None else None,
        "coverage": str(outcome.coverage),
        "coverage_state": outcome.coverage_state,
        "confidence_score": str(outcome.confidence_score),
        "confidence_state": outcome.confidence_state,
        "limitations": outcome.limitations,
        "configuration_hash": outcome.configuration_hash,
        "input_fingerprint": outcome.input_fingerprint,
        "output_fingerprint": outcome.output_fingerprint,
        "parameters": [
            {
                "key": p.parameter_key,
                "score": str(p.score) if p.score is not None else None,
                "status": p.status,
                "effective_weight": str(p.effective_weight),
                "contribution": str(p.contribution) if p.contribution is not None else None,
            }
            for p in outcome.parameter_results
        ],
    }

    fixture_payload = {
        "name": name,
        "description": desc,
        "model_config": cfg_dict,
        "variant_attributes": attrs,
        "evidence_records": ev_records,
        "is_valid": True,
        "expected_output": expected_out,
    }
    with open(FIXTURES_DIR / f"{name}.json", "w") as f:
        json.dump(fixture_payload, f, indent=2)
    print(f"Generated {name}.json")


if __name__ == "__main__":
    generate_all()

