"""JSON-Schema validation for inbound M2M messages."""

import json
from functools import lru_cache
from pathlib import Path
from typing import Any

import jsonschema

# ---------------------------------------------------------------------------
# Schema loading
# ---------------------------------------------------------------------------

_SCHEMA_DIR = Path(__file__).resolve().parent.parent.parent / "schemas"


@lru_cache(maxsize=8)
def _load_schema(version: str) -> dict:
    """Load and cache a schema JSON file by version string (e.g. '1.0')."""
    # Normalise '1.0' -> 'v1.json'
    major = version.split(".")[0]
    schema_path = _SCHEMA_DIR / f"v{major}.json"
    if not schema_path.exists():
        raise FileNotFoundError(f"Schema file not found: {schema_path}")
    with open(schema_path, "r", encoding="utf-8") as fh:
        return json.load(fh)


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------

class ValidationError(Exception):
    """Raised when a message fails schema validation."""

    def __init__(self, message: str, details: list[str] | None = None):
        super().__init__(message)
        self.details = details or []


def validate_message(data: Any) -> dict:
    """
    Validate *data* (a parsed JSON object / dict) against the schema
    indicated by data["schema_version"].

    Returns the validated dict unchanged on success.
    Raises ValidationError on failure.
    """
    if not isinstance(data, dict):
        raise ValidationError("Message must be a JSON object.", ["Root element is not an object."])

    version = data.get("schema_version")
    if not version:
        raise ValidationError(
            "Missing 'schema_version' field.",
            ["Field 'schema_version' is required to select the correct schema."],
        )

    try:
        schema = _load_schema(version)
    except FileNotFoundError as exc:
        raise ValidationError(f"Unknown schema version: {version!r}", [str(exc)]) from exc

    validator = jsonschema.Draft7Validator(schema)
    errors = sorted(validator.iter_errors(data), key=lambda e: list(e.path))
    if errors:
        details = [f"{list(e.path) or 'root'}: {e.message}" for e in errors]
        raise ValidationError(
            f"Message validation failed ({len(errors)} error(s)).", details
        )

    return data
