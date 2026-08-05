from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from typing import Any, Iterable

from jsonschema import Draft202012Validator

from .canonical import canonical_sha256

ROOT = Path(__file__).resolve().parents[2]
INPUT_SCHEMA_PATH = ROOT / "contracts/audio-stem-section-input.v0.1.schema.json"
RESULT_SCHEMA_PATH = ROOT / "contracts/audio-stem-section-result.v0.1.schema.json"
PROFILE_ID = "slice2-stem-section-v0.1"
PROFILE_CHECKSUM = "26ac1b86891a8dd7775a3b25bdb7f4b00d9ab284c7575815ce43c5f14e19680f"
TOOL_IDENTITY = "audio.stem_section_analyze"
EXPECTED_TARGETS = ["vocals", "drums", "bass", "other"]
FORBIDDEN_BLIND_KEYS = {
    "prompt",
    "prompts",
    "lyrics",
    "lyric",
    "genre",
    "genres",
    "persona",
    "personas",
    "claimed_section",
    "claimed_sections",
    "section_label",
    "section_labels",
    "semantic_label",
    "semantic_labels",
}
HEX64 = re.compile(r"^[0-9a-f]{64}$")
RECEIPT_FIELDS = {
    "status": re.compile(r"^- \*\*Status:\*\* `([^`]+)`$", re.MULTILINE),
    "scope": re.compile(r"^- \*\*Scope:\*\* `([^`]+)`$", re.MULTILINE),
    "track": re.compile(r"^- \*\*Track:\*\* `([^`]+)`$", re.MULTILINE),
    "profile_id": re.compile(r"^- \*\*Profile:\*\* `([^`]+)`$", re.MULTILINE),
    "source_sha256": re.compile(r"^- \*\*Source SHA-256:\*\* `([0-9a-f]{64})`$", re.MULTILINE),
}
RUN_ID_PATTERN = re.compile(r"^# Slice 1 Run Receipt: (S1-[A-Za-z0-9._-]+)$", re.MULTILINE)


class AudioRuntimeError(ValueError):
    """Fail-closed error raised by the bounded audio runtime core."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message


def _load_json_object(path: Path, code: str) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise AudioRuntimeError(code, f"file not found: {path}") from exc
    except json.JSONDecodeError as exc:
        raise AudioRuntimeError(code, f"invalid JSON in {path}: {exc}") from exc
    if not isinstance(value, dict):
        raise AudioRuntimeError(code, f"JSON root must be an object: {path}")
    return value


def _schema_errors(schema_path: Path, instance: dict[str, Any]) -> list[str]:
    schema = _load_json_object(schema_path, "CONTRACT_SCHEMA_INVALID")
    Draft202012Validator.check_schema(schema)
    errors = sorted(
        Draft202012Validator(schema).iter_errors(instance),
        key=lambda error: (list(error.absolute_path), error.message),
    )
    return [f"{'.'.join(str(part) for part in error.absolute_path) or '<root>'}: {error.message}" for error in errors]


def validate_request_contract(payload: dict[str, Any]) -> None:
    errors = _schema_errors(INPUT_SCHEMA_PATH, payload)
    if errors:
        raise AudioRuntimeError("REQUEST_CONTRACT_INVALID", "; ".join(errors))


def validate_result_contract(result: dict[str, Any]) -> None:
    errors = _schema_errors(RESULT_SCHEMA_PATH, result)
    if errors:
        raise AudioRuntimeError("RESULT_CONTRACT_INVALID", "; ".join(errors))


def _normalized_key(value: str) -> str:
    return value.strip().lower().replace("-", "_").replace(" ", "_")


def _walk_keys(value: Any, prefix: str = "") -> Iterable[tuple[str, str]]:
    if isinstance(value, dict):
        for key, child in value.items():
            key_text = str(key)
            path = f"{prefix}.{key_text}" if prefix else key_text
            yield path, _normalized_key(key_text)
            yield from _walk_keys(child, path)
    elif isinstance(value, list):
        for index, child in enumerate(value):
            yield from _walk_keys(child, f"{prefix}[{index}]")


def reject_prompt_leak(payload: dict[str, Any]) -> None:
    leaks = [path for path, key in _walk_keys(payload) if key in FORBIDDEN_BLIND_KEYS]
    if leaks:
        raise AudioRuntimeError("PROMPT_LEAK_INTO_BLIND_PASS", f"forbidden blind-stage fields: {', '.join(leaks)}")


def _require_absolute(path: Path, label: str) -> Path:
    if not path.is_absolute():
        raise AudioRuntimeError("PATH_NOT_ABSOLUTE", f"{label} must be absolute: {path}")
    return path


def _reject_symlink_components(path: Path, label: str, include_leaf: bool = True) -> None:
    current = Path(path.anchor)
    parts = path.parts[1:] if path.anchor else path.parts
    for index, part in enumerate(parts):
        current = current / part
        if not include_leaf and index == len(parts) - 1:
            break
        if current.exists() and current.is_symlink():
            raise AudioRuntimeError("SYMLINK_BOUNDARY_REJECTED", f"{label} contains symlink component: {current}")


def _existing_file(raw: str, label: str) -> Path:
    path = _require_absolute(Path(raw), label)
    _reject_symlink_components(path, label)
    if not path.is_file():
        raise AudioRuntimeError("FILE_REQUIRED", f"{label} must be an existing file: {path}")
    return path.resolve(strict=True)


def _existing_directory(raw: str, label: str) -> Path:
    path = _require_absolute(Path(raw), label)
    _reject_symlink_components(path, label)
    if not path.is_dir():
        raise AudioRuntimeError("DIRECTORY_REQUIRED", f"{label} must be an existing directory: {path}")
    return path.resolve(strict=True)


def sha256_file(path: Path) -> tuple[str, int]:
    digest = hashlib.sha256()
    byte_size = 0
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            byte_size += len(chunk)
            digest.update(chunk)
    return digest.hexdigest(), byte_size


def _verify_hash_and_size(path: Path, expected_sha256: str, expected_size: int, label: str) -> dict[str, Any]:
    if not HEX64.fullmatch(expected_sha256):
        raise AudioRuntimeError("INVALID_EXPECTED_HASH", f"invalid expected SHA-256 for {label}")
    actual_sha256, actual_size = sha256_file(path)
    if actual_sha256 != expected_sha256:
        raise AudioRuntimeError(
            "ARTIFACT_CHECKSUM_MISMATCH",
            f"SHA-256 mismatch for {label}: expected {expected_sha256}, got {actual_sha256}",
        )
    if actual_size != expected_size:
        raise AudioRuntimeError(
            "ARTIFACT_SIZE_MISMATCH",
            f"byte-size mismatch for {label}: expected {expected_size}, got {actual_size}",
        )
    return {"filename": path.name, "sha256": actual_sha256, "byte_size": actual_size}


def parse_slice1_receipt(path: Path) -> dict[str, str]:
    try:
        text = path.read_text(encoding="utf-8")
    except UnicodeDecodeError as exc:
        raise AudioRuntimeError("SLICE1_RECEIPT_INVALID", f"Slice 1 receipt is not UTF-8 text: {path}") from exc
    run_match = RUN_ID_PATTERN.search(text)
    if run_match is None:
        raise AudioRuntimeError("SLICE1_RECEIPT_INVALID", "Slice 1 receipt run ID is missing")
    values = {"run_id": run_match.group(1)}
    for name, pattern in RECEIPT_FIELDS.items():
        match = pattern.search(text)
        if match is None:
            raise AudioRuntimeError("SLICE1_RECEIPT_INVALID", f"Slice 1 receipt field is missing: {name}")
        values[name] = match.group(1)
    if "Evidence class remains `STONE_CANDIDATE`." not in text:
        raise AudioRuntimeError("SLICE1_RECEIPT_INVALID", "Slice 1 receipt does not preserve STONE_CANDIDATE evidence")
    if "Canon promotion remains disabled." not in text:
        raise AudioRuntimeError("SLICE1_RECEIPT_INVALID", "Slice 1 receipt does not keep canon promotion disabled")
    return values


def verify_slice1_dependency(payload: dict[str, Any], receipt_path: Path) -> dict[str, Any]:
    receipt = parse_slice1_receipt(receipt_path)
    if receipt["status"] != "COMPLETE":
        raise AudioRuntimeError("SLICE1_DEPENDENCY_INCOMPLETE", f"Slice 1 status is {receipt['status']}")
    if receipt["profile_id"] != "slice1-baseline-v0.1":
        raise AudioRuntimeError("SLICE1_PROFILE_MISMATCH", f"unexpected Slice 1 profile: {receipt['profile_id']}")
    if receipt["run_id"] != payload["slice1_run_id"]:
        raise AudioRuntimeError("SLICE1_RUN_ID_MISMATCH", "Slice 1 run ID does not match the request")
    if payload["slice1_source_sha256"] != payload["source_sha256"]:
        raise AudioRuntimeError("SLICE1_SOURCE_MISMATCH", "request source and Slice 1 source checksums differ")
    if receipt["source_sha256"] != payload["source_sha256"]:
        raise AudioRuntimeError("SLICE1_SOURCE_MISMATCH", "Slice 1 receipt source checksum differs")
    return {
        "run_id": receipt["run_id"],
        "status": receipt["status"],
        "profile_id": receipt["profile_id"],
        "source_sha256": receipt["source_sha256"],
        "receipt_path": str(receipt_path),
        "evidence_class": "DEPENDENCY_VERIFICATION",
    }


def verify_frozen_profile(payload: dict[str, Any], profile_path: Path) -> dict[str, Any]:
    profile = _load_json_object(profile_path, "PROFILE_INVALID")
    if profile.get("profile_id") != PROFILE_ID or profile.get("tool_identity") != TOOL_IDENTITY:
        raise AudioRuntimeError("PROFILE_IDENTITY_MISMATCH", "frozen profile identity mismatch")
    if profile.get("profile_state") != "FROZEN_NOT_RUNTIME_ADMITTED":
        raise AudioRuntimeError("PROFILE_STATE_INVALID", "unexpected frozen profile state")
    if profile.get("profile_checksum_algorithm") != "sha256-canonical-json-v1":
        raise AudioRuntimeError("PROFILE_ALGORITHM_INVALID", "unsupported profile checksum algorithm")
    recorded = profile.get("profile_checksum")
    unsigned = {key: value for key, value in profile.items() if key not in {"profile_checksum", "profile_checksum_algorithm"}}
    actual = canonical_sha256(unsigned)
    if actual != recorded:
        raise AudioRuntimeError("PROFILE_CHECKSUM_MISMATCH", f"profile checksum mismatch: expected {recorded}, got {actual}")
    if recorded != payload["profile_checksum"]:
        raise AudioRuntimeError("PROFILE_CHECKSUM_MISMATCH", "request checksum differs from frozen profile")
    if payload["profile_id"] != PROFILE_ID:
        raise AudioRuntimeError("PROFILE_IDENTITY_MISMATCH", "request profile ID differs")
    inference = profile.get("inference")
    if not isinstance(inference, dict):
        raise AudioRuntimeError("PROFILE_INVALID", "profile inference block is missing")
    if inference.get("targets") != EXPECTED_TARGETS:
        raise AudioRuntimeError("PROFILE_INVALID", "profile target order differs")
    if inference.get("network_during_analysis") is not False:
        raise AudioRuntimeError("NETWORK_POLICY_VIOLATION", "analysis profile must remain offline")
    if inference.get("authority_transfer") is not False:
        raise AudioRuntimeError("AUTHORITY_TRANSFER_BLOCKED", "profile authority_transfer must be false")
    return profile


def verify_model_cache(profile: dict[str, Any], cache_directory: Path) -> dict[str, Any]:
    package = profile.get("package")
    weights = profile.get("weights")
    if not isinstance(package, dict) or not isinstance(weights, list) or len(weights) != 4:
        raise AudioRuntimeError("PROFILE_INVALID", "package or four-weight lock is missing")
    if [item.get("target") for item in weights] != EXPECTED_TARGETS:
        raise AudioRuntimeError("PROFILE_INVALID", "weight target order differs")
    package_path = cache_directory / "package" / str(package.get("filename", ""))
    _reject_symlink_components(package_path, "package artifact")
    if not package_path.is_file():
        raise AudioRuntimeError("MODEL_PACKAGE_MISSING", f"locked package is missing: {package_path}")
    verified_package = _verify_hash_and_size(
        package_path,
        str(package.get("sha256", "")),
        int(package.get("byte_size", 0)),
        "openunmix package",
    )
    verified_weights: list[dict[str, Any]] = []
    for item in weights:
        target = str(item.get("target", ""))
        weight_path = cache_directory / "weights" / str(item.get("filename", ""))
        _reject_symlink_components(weight_path, f"{target} weight")
        if not weight_path.is_file():
            raise AudioRuntimeError("MODEL_WEIGHT_MISSING", f"locked weight is missing: {weight_path}")
        verified = _verify_hash_and_size(
            weight_path,
            str(item.get("sha256", "")),
            int(item.get("byte_size", 0)),
            f"{target} weight",
        )
        verified_weights.append({"target": target, **verified})
    return {
        "directory": str(cache_directory),
        "package": verified_package,
        "weights": verified_weights,
        "network_during_analysis": False,
        "evidence_class": "ENVIRONMENT_RECEIPT",
    }


def verify_output_boundary(raw: str) -> dict[str, Any]:
    output = _require_absolute(Path(raw), "output_directory")
    _reject_symlink_components(output, "output_directory", include_leaf=False)
    parent = output.parent
    if not parent.is_dir():
        raise AudioRuntimeError("OUTPUT_PARENT_MISSING", f"output parent must exist: {parent}")
    if output.exists():
        raise AudioRuntimeError("OUTPUT_OVERWRITE_BLOCKED", f"output directory already exists: {output}")
    resolved_parent = parent.resolve(strict=True)
    candidate = resolved_parent / output.name
    return {
        "output_directory": str(candidate),
        "parent_directory": str(resolved_parent),
        "overwrite_allowed": False,
        "state": "PRECHECKED",
        "evidence_class": "EXECUTION_CONTROL",
    }


def preflight_audio_runtime(payload: dict[str, Any]) -> dict[str, Any]:
    """Verify all immutable dependencies without loading a model or writing artifacts."""
    validate_request_contract(payload)
    reject_prompt_leak(payload)

    source_path = _existing_file(payload["source_audio_path"], "source_audio_path")
    source_sha256, source_size = sha256_file(source_path)
    if source_sha256 != payload["source_sha256"]:
        raise AudioRuntimeError(
            "SOURCE_CHECKSUM_MISMATCH",
            f"source checksum mismatch: expected {payload['source_sha256']}, got {source_sha256}",
        )

    receipt_path = _existing_file(payload["slice1_receipt_path"], "slice1_receipt_path")
    slice1_dependency = verify_slice1_dependency(payload, receipt_path)
    profile_path = _existing_file(payload["profile_path"], "profile_path")
    profile = verify_frozen_profile(payload, profile_path)
    model_cache = _existing_directory(payload["model_cache_directory"], "model_cache_directory")
    model_cache_result = verify_model_cache(profile, model_cache)
    output_transaction = verify_output_boundary(payload["output_directory"])

    result = {
        "status": "PRECHECK_COMPLETE",
        "tool_identity": TOOL_IDENTITY,
        "profile_id": PROFILE_ID,
        "profile_checksum": PROFILE_CHECKSUM,
        "source_dependency": {
            "path": str(source_path),
            "sha256": source_sha256,
            "byte_size": source_size,
            "evidence_class": "SOURCE_PROVENANCE",
        },
        "slice1_dependency": slice1_dependency,
        "model_cache": model_cache_result,
        "output_transaction": output_transaction,
        "runtime_admission": False,
        "pilot_authorized": False,
        "authority_transfer": False,
    }
    validate_result_contract(result)
    return result
