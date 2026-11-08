"""Contract validation tests for smartphone-extraction-1.0.schema.json."""

from copy import deepcopy
from typing import Any

import pytest

from app.schemas.contract_validator import (
    ContractValidationError,
    assert_valid_contract_payload,
    validate_contract_payload,
)

VALID_PAYLOAD: dict[str, Any] = {
    "schema_version": "1.0",
    "record_id": "550e8400-e29b-41d4-a716-446655440000",
    "source": {
        "marketplace": "amazon.in",
        "product_url": "https://www.amazon.in/dp/B0CS6DY3T7",
        "extracted_at": "2026-11-08T01:00:00Z",
        "extraction_method": "browser_extension_user_initiated",
        "extension_version": "1.0.0",
        "page_title": "Samsung Galaxy S24 Ultra 5G (Titanium Black, 12GB, 256GB Storage)",
        "asin": "B0CS6DY3T7",
    },
    "raw_extraction": {
        "title": "Samsung Galaxy S24 Ultra 5G (Titanium Black, 12GB, 256GB Storage)",
        "brand_text": "Samsung",
        "model_text": "Galaxy S24 Ultra",
        "variant_text": "12GB RAM, 256GB Storage",
        "price_text": "₹1,29,999",
        "rating_text": "4.5 out of 5 stars",
        "review_count_text": "1,520 ratings",
        "availability_text": "In stock",
        "specifications_text": [
            {"label": "Brand", "value": "Samsung"},
            {"label": "Model Name", "value": "Galaxy S24 Ultra"},
            {"label": "RAM", "value": "12 GB"},
            {"label": "Memory Storage Capacity", "value": "256 GB"},
        ],
    },
    "normalized": {
        "category": "smartphone",
        "brand": "Samsung",
        "model_name": "Galaxy S24 Ultra",
        "model_number": "SM-S928B",
        "ram_gb": 12,
        "storage_gb": 256,
        "display_size_inches": 6.8,
        "battery_capacity_mah": 5000,
        "operating_system": "Android 14",
        "processor": "Snapdragon 8 Gen 3",
        "supports_5g": True,
        "price_amount": 129999.0,
        "currency": "INR",
        "rating": 4.5,
        "review_count": 1520,
        "availability": "in_stock",
    },
    "validation": {
        "status": "valid",
        "identity_status": "identified",
        "warnings": [],
        "errors": [],
    },
}


def test_valid_approved_payload_passes():
    """Verify that a compliant smartphone extraction payload validates cleanly."""
    is_valid, errors = validate_contract_payload(VALID_PAYLOAD)
    assert is_valid, f"Expected valid payload, got errors: {errors}"
    assert len(errors) == 0
    # Should not raise
    assert_valid_contract_payload(VALID_PAYLOAD)


def test_unsupported_contract_version_rejected():
    """Verify that schema_version other than '1.0' is rejected."""
    payload = deepcopy(VALID_PAYLOAD)
    payload["schema_version"] = "2.0"
    is_valid, errors = validate_contract_payload(payload)
    assert not is_valid
    assert any("schema_version" in e for e in errors)
    with pytest.raises(ContractValidationError):
        assert_valid_contract_payload(payload)


def test_missing_required_top_level_section_rejected():
    """Verify that missing raw_extraction or normalized is rejected."""
    payload = deepcopy(VALID_PAYLOAD)
    del payload["raw_extraction"]
    is_valid, errors = validate_contract_payload(payload)
    assert not is_valid
    assert any("raw_extraction" in e for e in errors)


def test_wrong_field_type_rejected():
    """Verify string passed for numeric field is rejected."""
    payload = deepcopy(VALID_PAYLOAD)
    payload["normalized"]["ram_gb"] = "12GB"  # string instead of number
    is_valid, errors = validate_contract_payload(payload)
    assert not is_valid
    assert any("ram_gb" in e for e in errors)


def test_invalid_negative_numeric_rejected():
    """Verify negative prices or storage violate minimum bounds."""
    payload = deepcopy(VALID_PAYLOAD)
    payload["normalized"]["price_amount"] = -100.0
    is_valid, errors = validate_contract_payload(payload)
    assert not is_valid
    assert any("price_amount" in e for e in errors)


def test_unknown_additional_property_rejected():
    """Verify that additionalProperties: false is strictly enforced at all levels."""
    payload = deepcopy(VALID_PAYLOAD)
    payload["unexpected_injected_field"] = "malicious"
    is_valid, errors = validate_contract_payload(payload)
    assert not is_valid
    assert any("unexpected_injected_field" in e for e in errors)


def test_invalid_marketplace_rejected():
    """Verify non-Amazon marketplace is rejected by schema constraint."""
    payload = deepcopy(VALID_PAYLOAD)
    payload["source"]["marketplace"] = "flipkart.com"
    is_valid, errors = validate_contract_payload(payload)
    assert not is_valid
    assert any("marketplace" in e for e in errors)


def test_non_inr_currency_rejected():
    """Verify currency must be INR or null."""
    payload = deepcopy(VALID_PAYLOAD)
    payload["normalized"]["currency"] = "USD"
    is_valid, errors = validate_contract_payload(payload)
    assert not is_valid
    assert any("currency" in e for e in errors)

