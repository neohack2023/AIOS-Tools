from __future__ import annotations

from typing import Any

from jsonschema import Draft202012Validator
from jsonschema.exceptions import SchemaError

from .canonical import canonical_sha256


TOOL_REGISTRY: dict[str, dict[str, Any]] = {
    "system.health": {"version": "0.1.0", "mode": "READ_ONLY", "description": "Report AIOS-Tools execution-layer state."},
    "canonical.hash_json": {"version": "0.1.0", "mode": "READ_ONLY", "description": "Produce a deterministic SHA-256 digest for JSON-compatible data."},
    "schema.validate": {"version": "0.1.0", "mode": "READ_ONLY", "description": "Validate an instance with JSON Schema Draft 2020-12."},
}


def system_health(payload: dict[str, Any]) -> dict[str, Any]:
    return {"service": "AIOS-Tools", "version": "0.1.0", "state": "BOOTSTRAP_OPERATIONAL", "default_mode": "READ_ONLY", "tools": TOOL_REGISTRY, "portable_repo_required": False, "authority_role": "EXECUTION_INFRASTRUCTURE"}


def hash_json(payload: dict[str, Any]) -> dict[str, Any]:
    if "value" not in payload:
        raise ValueError("input must contain 'value'")
    return {"algorithm": "sha256-canonical-json-v1", "digest": canonical_sha256(payload["value"])}


def validate_schema(payload: dict[str, Any]) -> dict[str, Any]:
    if "schema" not in payload or "instance" not in payload:
        raise ValueError("input must contain 'schema' and 'instance'")
    schema = payload["schema"]
    instance = payload["instance"]
    try:
        Draft202012Validator.check_schema(schema)
    except SchemaError as exc:
        return {"valid": False, "schema_valid": False, "errors": [{"validator": "schema", "path": list(exc.path), "schema_path": list(exc.schema_path), "message": exc.message}]}
    validator = Draft202012Validator(schema)
    errors = sorted(validator.iter_errors(instance), key=lambda error: list(error.absolute_path))
    return {"valid": not errors, "schema_valid": True, "draft": "2020-12", "errors": [{"validator": error.validator, "path": list(error.absolute_path), "schema_path": list(error.absolute_schema_path), "message": error.message} for error in errors]}


HANDLERS = {"system.health": system_health, "canonical.hash_json": hash_json, "schema.validate": validate_schema}
