"""Unit definition, registry, and conversion engine using Pint.

Enforces physical dimension compatibility, distinguishes decimal vs. binary storage units
(e.g., GB vs GiB, TB vs TiB), preserves original source values, and computes deterministic
canonical values avoiding floating-point drift.
"""

import logging
from decimal import ROUND_HALF_UP, Decimal, InvalidOperation
from typing import NamedTuple

import pint

logger = logging.getLogger("review_master.units")

# Initialize shared Pint UnitRegistry
ureg = pint.UnitRegistry()
# Define domain-specific non-standard units if not built-in
try:
    ureg.define("milliampere_hour = milliampere * hour = mAh")
except pint.errors.RedefinitionError:
    pass


class ConversionResult(NamedTuple):
    """Result of unit conversion and normalization."""

    raw_value: str
    original_value: Decimal | None
    original_unit: str | None
    canonical_value: Decimal | None
    canonical_unit: str | None
    dimension: str
    is_valid: bool
    error: str | None = None


# Supported physical dimensions and their canonical base units
DIMENSION_CANONICAL_UNITS: dict[str, str] = {
    "storage": "GB",  # Decimal gigabytes
    "storage_binary": "GiB",  # Binary gibibytes
    "length": "inch",  # Display diagonal in inches
    "charge": "mAh",  # Battery capacity in milliampere-hours
    "mass": "g",  # Weight in grams
    "frequency": "GHz",  # Clock speed in gigahertz
    "power": "W",  # Power / charging in watts
}

# Unit alias mapping to Pint-compatible names and dimensions
UNIT_METADATA: dict[str, dict[str, str]] = {
    # Decimal storage
    "b": {"pint_name": "byte", "dimension": "storage", "canonical": "GB"},
    "byte": {"pint_name": "byte", "dimension": "storage", "canonical": "GB"},
    "bytes": {"pint_name": "byte", "dimension": "storage", "canonical": "GB"},
    "kb": {"pint_name": "kilobyte", "dimension": "storage", "canonical": "GB"},
    "mb": {"pint_name": "megabyte", "dimension": "storage", "canonical": "GB"},
    "gb": {"pint_name": "gigabyte", "dimension": "storage", "canonical": "GB"},
    "tb": {"pint_name": "terabyte", "dimension": "storage", "canonical": "GB"},
    "pb": {"pint_name": "petabyte", "dimension": "storage", "canonical": "GB"},
    # Binary storage
    "kib": {"pint_name": "kibibyte", "dimension": "storage_binary", "canonical": "GiB"},
    "mib": {"pint_name": "mebibyte", "dimension": "storage_binary", "canonical": "GiB"},
    "gib": {"pint_name": "gibibyte", "dimension": "storage_binary", "canonical": "GiB"},
    "tib": {"pint_name": "tebibyte", "dimension": "storage_binary", "canonical": "GiB"},
    # Length / display
    "in": {"pint_name": "inch", "dimension": "length", "canonical": "inch"},
    "inch": {"pint_name": "inch", "dimension": "length", "canonical": "inch"},
    "inches": {"pint_name": "inch", "dimension": "length", "canonical": "inch"},
    "cm": {"pint_name": "centimeter", "dimension": "length", "canonical": "inch"},
    "mm": {"pint_name": "millimeter", "dimension": "length", "canonical": "inch"},
    # Battery charge
    "mah": {"pint_name": "mAh", "dimension": "charge", "canonical": "mAh"},
    "ah": {"pint_name": "ampere * hour", "dimension": "charge", "canonical": "mAh"},
    # Mass / weight
    "g": {"pint_name": "gram", "dimension": "mass", "canonical": "g"},
    "gram": {"pint_name": "gram", "dimension": "mass", "canonical": "g"},
    "grams": {"pint_name": "gram", "dimension": "mass", "canonical": "g"},
    "kg": {"pint_name": "kilogram", "dimension": "mass", "canonical": "g"},
    "oz": {"pint_name": "ounce", "dimension": "mass", "canonical": "g"},
    "lb": {"pint_name": "pound", "dimension": "mass", "canonical": "g"},
    # Frequency
    "ghz": {"pint_name": "gigahertz", "dimension": "frequency", "canonical": "GHz"},
    "mhz": {"pint_name": "megahertz", "dimension": "frequency", "canonical": "GHz"},
    # Power
    "w": {"pint_name": "watt", "dimension": "power", "canonical": "W"},
    "watt": {"pint_name": "watt", "dimension": "power", "canonical": "W"},
    "watts": {"pint_name": "watt", "dimension": "power", "canonical": "W"},
}


class UnitNormalizer:
    """Deterministic physical measurement normalizer."""

    @staticmethod
    def normalize(
        value: Decimal | float | str | None,
        unit: str | None,
        target_canonical_unit: str | None = None,
    ) -> ConversionResult:
        """Normalize a value and unit into its canonical representation.

        Args:
            value: The numeric value (can be None for unknown).
            unit: The original unit string (e.g. "TB", "GB", "cm", "inches").
            target_canonical_unit: Optional specific canonical unit override.

        Returns:
            ConversionResult with original and canonical values.
        """
        raw_repr = (
            f"{value} {unit}".strip()
            if value is not None and unit
            else (str(value) if value is not None else "")
        )
        if value is None:
            return ConversionResult(
                raw_value=raw_repr,
                original_value=None,
                original_unit=unit,
                canonical_value=None,
                canonical_unit=target_canonical_unit,
                dimension="unknown",
                is_valid=True,
            )

        try:
            dec_value = Decimal(str(value))
        except (InvalidOperation, ValueError, TypeError):
            return ConversionResult(
                raw_value=raw_repr,
                original_value=None,
                original_unit=unit,
                canonical_value=None,
                canonical_unit=target_canonical_unit,
                dimension="unknown",
                is_valid=False,
                error=f"Invalid numeric value: {value}",
            )

        if not unit:
            # Dimensionless number
            return ConversionResult(
                raw_value=raw_repr,
                original_value=dec_value,
                original_unit=None,
                canonical_value=dec_value,
                canonical_unit=None,
                dimension="dimensionless",
                is_valid=True,
            )

        unit_clean = unit.strip().lower()
        meta = UNIT_METADATA.get(unit_clean)

        if not meta:
            # Try to resolve through Pint directly
            try:
                pint_unit = ureg.parse_units(unit)
                dimension = str(pint_unit.dimensionality)
                canonical = target_canonical_unit or str(pint_unit)
                # Attempt conversion if target provided
                if target_canonical_unit:
                    q = dec_value * pint_unit
                    converted = q.to(target_canonical_unit)
                    canonical_dec = Decimal(str(converted.magnitude)).quantize(
                        Decimal("0.0001"), rounding=ROUND_HALF_UP
                    )
                else:
                    canonical_dec = dec_value

                return ConversionResult(
                    raw_value=raw_repr,
                    original_value=dec_value,
                    original_unit=unit,
                    canonical_value=canonical_dec,
                    canonical_unit=canonical,
                    dimension=dimension,
                    is_valid=True,
                )
            except (pint.errors.PintError, ValueError, TypeError) as e:
                return ConversionResult(
                    raw_value=raw_repr,
                    original_value=dec_value,
                    original_unit=unit,
                    canonical_value=None,
                    canonical_unit=target_canonical_unit,
                    dimension="unknown",
                    is_valid=False,
                    error=f"Unrecognized or unsupported unit '{unit}': {e}",
                )

        dimension = meta["dimension"]
        canonical_unit = target_canonical_unit or meta["canonical"]

        # Validate target compatibility if target was explicitly provided
        if target_canonical_unit:
            target_meta = UNIT_METADATA.get(target_canonical_unit.strip().lower())
            if target_meta and target_meta["dimension"] != dimension:
                # Disallow cross-dimension conversion (e.g. storage -> length)
                return ConversionResult(
                    raw_value=raw_repr,
                    original_value=dec_value,
                    original_unit=unit,
                    canonical_value=None,
                    canonical_unit=target_canonical_unit,
                    dimension=dimension,
                    is_valid=False,
                    error=f"Incompatible unit dimension: cannot convert {unit} ({dimension}) to {target_canonical_unit} ({target_meta['dimension']})",
                )

        # Precise conversion using Decimal for standard units
        try:
            canonical_dec = UnitNormalizer._convert_deterministic(
                dec_value, unit_clean, canonical_unit.strip().lower()
            )
        except (ValueError, KeyError):
            # Fallback to Pint conversion
            try:
                q = float(dec_value) * ureg(meta["pint_name"])
                target_pint = UNIT_METADATA.get(canonical_unit.strip().lower(), {}).get(
                    "pint_name", canonical_unit
                )
                converted_q = q.to(target_pint)
                canonical_dec = Decimal(str(converted_q.magnitude)).quantize(
                    Decimal("0.0001"), rounding=ROUND_HALF_UP
                )
            except (pint.errors.PintError, ValueError, TypeError) as e:
                return ConversionResult(
                    raw_value=raw_repr,
                    original_value=dec_value,
                    original_unit=unit,
                    canonical_value=None,
                    canonical_unit=canonical_unit,
                    dimension=dimension,
                    is_valid=False,
                    error=f"Conversion error from {unit} to {canonical_unit}: {e}",
                )

        return ConversionResult(
            raw_value=raw_repr,
            original_value=dec_value,
            original_unit=unit,
            canonical_value=canonical_dec,
            canonical_unit=canonical_unit,
            dimension=dimension,
            is_valid=True,
        )

    @staticmethod
    def _convert_deterministic(val: Decimal, from_unit: str, to_unit: str) -> Decimal:
        """Deterministic exact Decimal conversions avoiding IEEE 754 float drift."""
        # Decimal storage conversion to GB
        if to_unit == "gb":
            factors_to_gb = {
                "b": Decimal(1) / Decimal(1000000000),
                "byte": Decimal(1) / Decimal(1000000000),
                "kb": Decimal(1) / Decimal(1000000),
                "mb": Decimal(1) / Decimal(1000),
                "gb": Decimal(1),
                "tb": Decimal(1000),
                "pb": Decimal(1000000),
            }
            if from_unit in factors_to_gb:
                return (val * factors_to_gb[from_unit]).quantize(
                    Decimal("0.0001"), rounding=ROUND_HALF_UP
                )

        # Binary storage conversion to GiB
        if to_unit == "gib":
            factors_to_gib = {
                "b": Decimal(1) / Decimal(1073741824),
                "kib": Decimal(1) / Decimal(1048576),
                "mib": Decimal(1) / Decimal(1024),
                "gib": Decimal(1),
                "tib": Decimal(1024),
            }
            if from_unit in factors_to_gib:
                return (val * factors_to_gib[from_unit]).quantize(
                    Decimal("0.0001"), rounding=ROUND_HALF_UP
                )

        # Length conversion to inch
        if to_unit in ("inch", "in", "inches"):
            if from_unit in ("inch", "in", "inches"):
                return val.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
            if from_unit == "cm":
                # 1 inch = 2.54 cm
                return (val / Decimal("2.54")).quantize(
                    Decimal("0.01"), rounding=ROUND_HALF_UP
                )
            if from_unit == "mm":
                return (val / Decimal("25.4")).quantize(
                    Decimal("0.01"), rounding=ROUND_HALF_UP
                )

        # Mass conversion to gram
        if to_unit in ("g", "gram", "grams"):
            if from_unit in ("g", "gram", "grams"):
                return val.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
            if from_unit == "kg":
                return (val * Decimal(1000)).quantize(
                    Decimal("0.01"), rounding=ROUND_HALF_UP
                )

        # Battery charge to mAh
        if to_unit == "mah":
            if from_unit == "mah":
                return val.quantize(Decimal(1), rounding=ROUND_HALF_UP)
            if from_unit == "ah":
                return (val * Decimal(1000)).quantize(
                    Decimal(1), rounding=ROUND_HALF_UP
                )

        raise ValueError(f"No direct deterministic rule from {from_unit} to {to_unit}")
