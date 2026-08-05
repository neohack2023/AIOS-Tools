from __future__ import annotations

from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator
from jsonschema.exceptions import SchemaError

from .audio_native_demucs import NativeDemucsProfile, run_native_demucs
from .canonical import canonical_sha256


def system_health(payload: dict[str, Any]) -> dict[str, Any]:
    return {
        "service": "AIOS-Tools",
        "version": "0.1.0",
        "state": "BOOTSTRAP_OPERATIONAL",
        "default_mode": "READ_ONLY",
        "portable_repo_required": False,
        "authority_role": "EXECUTION_INFRASTRUCTURE",
    }


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
        return {
            "valid": False,
            "schema_valid": False,
            "errors": [
                {
                    "validator": "schema",
                    "path": list(exc.path),
                    "schema_path": list(exc.schema_path),
                    "message": exc.message,
                }
            ],
        }
    validator = Draft202012Validator(schema)
    errors = sorted(validator.iter_errors(instance), key=lambda error: list(error.absolute_path))
    return {
        "valid": not errors,
        "schema_valid": True,
        "draft": "2020-12",
        "errors": [
            {
                "validator": error.validator,
                "path": list(error.absolute_path),
                "schema_path": list(error.absolute_schema_path),
                "message": error.message,
            }
            for error in errors
        ],
    }


def audio_demucs_separate(payload: dict[str, Any]) -> dict[str, Any]:
    required = {"source_path", "output_dir", "profile_path"}
    missing = sorted(required - payload.keys())
    if missing:
        raise ValueError(f"input missing fields: {', '.join(missing)}")

    profile = NativeDemucsProfile.from_json(Path(str(payload["profile_path"])))
    result = run_native_demucs(
        profile,
        Path(str(payload["source_path"])),
        Path(str(payload["output_dir"])),
    )
    return {
        **result,
        "workflow": "AUDIO_STEM_SECTION_ANALYSIS",
        "engine": "demucs",
        "profile_id": profile.profile_id,
        "evidence_class": "MODEL_ESTIMATE",
        "runtime_admission": False,
        "authority_transfer": False,
    }


HANDLERS = {
    "system.health": system_health,
    "canonical.hash_json": hash_json,
    "schema.validate": validate_schema,
    "audio.demucs.separate": audio_demucs_separate,
}
