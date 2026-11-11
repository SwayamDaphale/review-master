"""Deterministic fingerprinting service for canonical products and variants.

Provides reproducible, versioned hashes for catalog entities:
- Product fingerprint (v1): category, manufacturer, model name, model number.
- Variant fingerprint (v1): product reference + deterministic sorted normalized configuration.
"""

import hashlib
import json
import re
from typing import Any


def _normalize_string(val: str | None) -> str:
    """Normalize string by trimming, lowercasing, and collapsing whitespace."""
    if not val:
        return ""
    # Collapse multiple whitespaces and trim
    cleaned = re.sub(r"\s+", " ", val.strip())
    return cleaned.lower()


def _normalize_config_value(key: str, value: Any) -> Any:
    """Normalize configuration attribute value according to key type."""
    if value is None:
        return None
    if isinstance(value, (int, float)):
        # Normalize whole floats to int representation for stable hashing (e.g. 12.0 -> 12)
        if float(value).is_integer():
            return int(value)
        return round(float(value), 3)
    if isinstance(value, str):
        return _normalize_string(value)
    if isinstance(value, bool):
        return bool(value)
    return str(value)


class FingerprintService:
    """Service generating deterministic, reproducible fingerprints for products and variants."""

    ALGORITHM_VERSION = "v1"

    @classmethod
    def generate_product_fingerprint(
        cls,
        category: str,
        manufacturer: str,
        model_name: str,
        model_number: str | None = None,
    ) -> str:
        """Compute deterministic SHA-256 product fingerprint.

        Format: product_v1:{norm_category}:{norm_mfr}:{norm_model_name}:{norm_model_number}
        """
        norm_cat = _normalize_string(category)
        norm_mfr = _normalize_string(manufacturer)
        norm_model = _normalize_string(model_name)
        norm_num = _normalize_string(model_number)

        canonical_repr = (
            f"product_{cls.ALGORITHM_VERSION}:{norm_cat}:{norm_mfr}:{norm_model}:{norm_num}"
        )
        return hashlib.sha256(canonical_repr.encode("utf-8")).hexdigest()

    @classmethod
    def generate_variant_fingerprint(
        cls,
        product_fingerprint: str,
        configuration: dict[str, Any] | None,
    ) -> str:
        """Compute deterministic SHA-256 variant fingerprint incorporating product identity and sorted configuration.

        Missing or unknown attributes must NEVER be defaulted to zero or assumed matching.
        """
        if not configuration:
            canonical_json = "{}"
        else:
            # Filter and normalize attributes; preserve None or omit missing
            normalized_config: dict[str, Any] = {}
            for k, v in sorted(configuration.items()):
                if v is not None:
                    norm_k = _normalize_string(k)
                    normalized_config[norm_k] = _normalize_config_value(k, v)

            canonical_json = json.dumps(
                normalized_config,
                sort_keys=True,
                separators=(",", ":"),
                ensure_ascii=True,
            )

        canonical_repr = (
            f"variant_{cls.ALGORITHM_VERSION}:{product_fingerprint}:{canonical_json}"
        )
        return hashlib.sha256(canonical_repr.encode("utf-8")).hexdigest()

