"""JSON Schema Draft 2020-12 validator for the frozen smartphone extraction contract."""

import json
from pathlib import Path
from typing import Any

import jsonschema  # type: ignore[import-untyped]

SCHEMA_FILENAME = "smartphone-extraction-1.0.schema.json"


class ContractValidationError(Exception):
    """Raised when an extraction payload violates the frozen contract schema."""

    def __init__(self, message: str, errors: list[str] | None = None):
        super().__init__(message)
        self.errors = errors or [message]


def get_contract_schema_path() -> Path:
    """Resolve the filesystem path to smartphone-extraction-1.0.schema.json."""
    # 1. Check local backend package directory
    local_path = Path(__file__).parent / SCHEMA_FILENAME
    if local_path.exists():
        return local_path

    # 2. Check repo-level docs/schemas directory
    repo_docs_path = (
        Path(__file__).resolve().parents[3] / "docs" / "schemas" / SCHEMA_FILENAME
    )
    if repo_docs_path.exists():
        return repo_docs_path

    raise FileNotFoundError(
        f"Frozen contract schema '{SCHEMA_FILENAME}' not found in app/schemas or docs/schemas."
    )


def load_contract_schema() -> dict[str, Any]:
    """Load and parse the JSON Schema Draft 2020-12 definition."""
    schema_path = get_contract_schema_path()
    with open(schema_path, "r", encoding="utf-8") as f:
        schema: dict[str, Any] = json.load(f)
    return schema


# Cached compiled validator instance
_SCHEMA = load_contract_schema()
_VALIDATOR = jsonschema.Draft202012Validator(_SCHEMA)


def validate_contract_payload(payload: dict[str, Any]) -> tuple[bool, list[str]]:
    """Validate raw payload against the frozen JSON Schema.

    Returns:
        tuple[bool, list[str]]: (is_valid, list_of_error_messages)
    """
    errors: list[str] = []
    for err in sorted(_VALIDATOR.iter_errors(payload), key=lambda e: e.path):
        path = " -> ".join(str(p) for p in err.path) or "root"
        errors.append(f"[{path}] {err.message}")

    return (len(errors) == 0, errors)


def assert_valid_contract_payload(payload: dict[str, Any]) -> None:
    """Assert payload matches contract or raise ContractValidationError."""
    is_valid, errors = validate_contract_payload(payload)
    if not is_valid:
        raise ContractValidationError(
            f"Extraction payload failed contract validation ({len(errors)} errors)",
            errors=errors,
        )
