#!/usr/bin/env python3
"""Fail-closed verifier for the Slice 2A Open-Unmix model/profile lock.

No command in this module performs network access or changes runtime admission.
The verifier can validate the committed manifest, cross-check the frozen profile
and receipts, and independently hash a local quarantine directory.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from pathlib import Path
from typing import Any

EXPECTED_TARGETS = ["vocals", "drums", "bass", "other"]
PROFILE_ID = "slice2-stem-section-v0.1"
TOOL_IDENTITY = "audio.stem_section_analyze"
HEX32 = re.compile(r"^[0-9a-f]{32}$")
HEX64 = re.compile(r"^[0-9a-f]{64}$")


class VerificationError(ValueError):
    """Raised when model-lock evidence fails closed."""


def _load_json(path: Path) -> dict[str, Any]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise VerificationError(f"JSON file not found: {path}") from exc
    except json.JSONDecodeError as exc:
        raise VerificationError(f"invalid JSON in {path}: {exc}") from exc
    if not isinstance(data, dict):
        raise VerificationError(f"JSON root must be an object: {path}")
    return data


def _canonical_sha256(value: Any) -> str:
    payload = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def _hash_file(path: Path) -> tuple[str, str, int]:
    md5 = hashlib.md5(usedforsecurity=False)
    sha256 = hashlib.sha256()
    size = 0
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            size += len(chunk)
            md5.update(chunk)
            sha256.update(chunk)
    return md5.hexdigest(), sha256.hexdigest(), size


def _require_hex(value: Any, pattern: re.Pattern[str], label: str) -> str:
    if not isinstance(value, str) or not pattern.fullmatch(value):
        raise VerificationError(f"invalid {label}")
    return value


def _require_positive_int(value: Any, label: str) -> int:
    if not isinstance(value, int) or isinstance(value, bool) or value <= 0:
        raise VerificationError(f"invalid {label}")
    return value


def validate_manifest(data: dict[str, Any]) -> None:
    if data.get("schema_version") != "0.2.0":
        raise VerificationError("unsupported schema_version")
    if data.get("profile_id") != PROFILE_ID:
        raise VerificationError("unexpected profile_id")
    if data.get("tool_identity") != TOOL_IDENTITY:
        raise VerificationError("unexpected tool_identity")
    if data.get("status") != "PROFILE_LOCKED_RUNTIME_IMPLEMENTATION_REVIEW_REQUIRED":
        raise VerificationError("unexpected manifest status")

    authority = data.get("authority")
    if not isinstance(authority, dict) or authority.get("authority_transfer") is not False:
        raise VerificationError("authority_transfer must be false")
    expected_notion = "https://app.notion.com/p/3b343bd4ae4a817087f2fb9f56936545"
    if authority.get("notion_decision_candidate") != expected_notion:
        raise VerificationError("Notion decision-candidate URL is incorrect")

    runtime = data.get("runtime_reference")
    if not isinstance(runtime, dict) or runtime.get("network_during_analysis") is not False:
        raise VerificationError("analysis must remain offline")

    profile = data.get("inference_profile")
    if not isinstance(profile, dict):
        raise VerificationError("inference_profile must be an object")
    if profile.get("targets") != EXPECTED_TARGETS:
        raise VerificationError("inference target order must be vocals, drums, bass, other")
    if profile.get("residual") is not False:
        raise VerificationError("model residual must remain disabled")
    if profile.get("authority_transfer") is not False:
        raise VerificationError("profile authority_transfer must be false")
    if profile.get("network_during_analysis") is not False:
        raise VerificationError("profile analysis network must be false")

    package = data.get("package_artifact")
    if not isinstance(package, dict):
        raise VerificationError("package_artifact must be an object")
    _require_hex(package.get("provider_md5"), HEX32, "package provider_md5")
    _require_hex(package.get("sha256"), HEX64, "package sha256")
    _require_positive_int(package.get("byte_size"), "package byte_size")
    if package.get("locked") is not True:
        raise VerificationError("package artifact must be locked")
    if package.get("admitted_to_runtime_cache") is not False:
        raise VerificationError("package runtime-cache admission must remain false")

    weights = data.get("weights")
    if not isinstance(weights, list) or len(weights) != 4:
        raise VerificationError("exactly four weight entries are required")
    if [item.get("target") for item in weights] != EXPECTED_TARGETS:
        raise VerificationError("weight target order mismatch")
    filenames = [item.get("filename") for item in weights]
    if len(set(filenames)) != 4 or not all(isinstance(name, str) and name for name in filenames):
        raise VerificationError("weight filenames must be unique non-empty strings")
    for item in weights:
        target = item.get("target")
        _require_hex(item.get("provider_md5"), HEX32, f"provider_md5 for {target}")
        _require_hex(item.get("sha256"), HEX64, f"sha256 for {target}")
        _require_positive_int(item.get("byte_size"), f"byte_size for {target}")
        if item.get("locked") is not True:
            raise VerificationError(f"weight must be locked: {target}")
        if item.get("admitted_to_runtime_cache") is not False:
            raise VerificationError(f"weight runtime-cache admission must remain false: {target}")

    frozen = data.get("frozen_profile")
    if not isinstance(frozen, dict):
        raise VerificationError("frozen_profile must be an object")
    _require_hex(frozen.get("profile_checksum"), HEX64, "profile checksum")
    if frozen.get("profile_checksum_algorithm") != "sha256-canonical-json-v1":
        raise VerificationError("unsupported profile checksum algorithm")
    if frozen.get("injected_into_runtime") is not False:
        raise VerificationError("frozen profile must not claim runtime injection")

    review = data.get("runtime_review")
    if not isinstance(review, dict):
        raise VerificationError("runtime_review must be an object")
    if review.get("implementation_present") is not False:
        raise VerificationError("runtime implementation is not admitted in this slice")
    if review.get("runtime_admission") is not False or review.get("pilot_authorized") is not False:
        raise VerificationError("runtime and pilot gates must remain false")
    if review.get("decision") != "SEPARATE_BOUNDED_RUNTIME_IMPLEMENTATION_PR_REQUIRED":
        raise VerificationError("unexpected runtime review decision")

    gates = data.get("gates")
    if not isinstance(gates, dict):
        raise VerificationError("gates must be an object")
    required_true = (
        "baseline_approved",
        "runtime_compatibility_smoke_test",
        "package_artifact_locked",
        "all_weight_provider_checksums_verified",
        "all_weight_sha256_present",
        "resource_envelope_measured_with_pretrained_weights",
        "profile_checksum_frozen",
        "profile_injected_into_manifest",
        "runtime_review_completed",
    )
    for key in required_true:
        if gates.get(key) is not True:
            raise VerificationError(f"required completed gate is false: {key}")
    if gates.get("runtime_implementation_present") is not False:
        raise VerificationError("runtime_implementation_present must remain false")
    if gates.get("runtime_admission") is not False:
        raise VerificationError("runtime_admission must remain false")
    if gates.get("pilot_authorized") is not False:
        raise VerificationError("pilot_authorized must remain false")


def validate_frozen_profile(manifest: dict[str, Any], profile: dict[str, Any]) -> None:
    if profile.get("profile_id") != PROFILE_ID or profile.get("tool_identity") != TOOL_IDENTITY:
        raise VerificationError("frozen profile identity mismatch")
    if profile.get("profile_state") != "FROZEN_NOT_RUNTIME_ADMITTED":
        raise VerificationError("unexpected frozen profile state")
    algorithm = profile.get("profile_checksum_algorithm")
    checksum = _require_hex(profile.get("profile_checksum"), HEX64, "frozen profile checksum")
    if algorithm != "sha256-canonical-json-v1":
        raise VerificationError("unsupported frozen profile checksum algorithm")
    unsigned = {key: value for key, value in profile.items() if key not in {"profile_checksum", "profile_checksum_algorithm"}}
    actual = _canonical_sha256(unsigned)
    if actual != checksum:
        raise VerificationError(f"frozen profile checksum mismatch: expected {checksum}, got {actual}")
    if checksum != manifest["frozen_profile"]["profile_checksum"]:
        raise VerificationError("manifest/frozen-profile checksum mismatch")
    if profile.get("inference") != manifest.get("inference_profile"):
        raise VerificationError("manifest/frozen-profile inference mismatch")


def validate_resource_receipt(manifest: dict[str, Any], receipt: dict[str, Any]) -> None:
    if receipt.get("status") != "PROFILE_FROZEN_RESOURCE_ENVELOPE_MEASURED":
        raise VerificationError("unexpected resource receipt status")
    if receipt.get("run_classification") != "PRETRAINED_SYNTHETIC_CPU_RESOURCE_BENCHMARK":
        raise VerificationError("unexpected resource run classification")
    if receipt.get("authority_transfer") is not False:
        raise VerificationError("resource receipt authority_transfer must be false")
    if receipt.get("profile_checksum") != manifest["frozen_profile"]["profile_checksum"]:
        raise VerificationError("manifest/resource profile checksum mismatch")
    inference = receipt.get("inference")
    if not isinstance(inference, dict) or inference.get("finite_values") is not True:
        raise VerificationError("resource inference evidence is invalid")
    if inference.get("same_context_bit_identical") is not True or inference.get("same_context_max_abs_diff") != 0.0:
        raise VerificationError("same-context deterministic rerun did not pass")
    _require_positive_int(inference.get("peak_rss_bytes"), "resource peak_rss_bytes")
    disk = receipt.get("disk")
    if not isinstance(disk, dict):
        raise VerificationError("resource disk evidence missing")
    _require_positive_int(disk.get("combined_bytes"), "resource combined_bytes")


def validate_runtime_review(manifest: dict[str, Any], review: dict[str, Any]) -> None:
    if review.get("status") != "RUNTIME_IMPLEMENTATION_REVIEW_REQUIRED":
        raise VerificationError("unexpected runtime review status")
    if review.get("run_classification") != "STATIC_RUNTIME_ADMISSION_SURFACE_REVIEW":
        raise VerificationError("unexpected runtime review classification")
    if review.get("implementation_present") is not False:
        raise VerificationError("runtime review must report implementation absent")
    if review.get("decision") != manifest["runtime_review"]["decision"]:
        raise VerificationError("manifest/runtime-review decision mismatch")
    if review.get("runtime_admission") is not False or review.get("pilot_authorized") is not False:
        raise VerificationError("runtime review must fail closed")


def verify_weights(data: dict[str, Any], weights_dir: Path) -> dict[str, Any]:
    results: list[dict[str, Any]] = []
    for item in data["weights"]:
        path = weights_dir / item["filename"]
        if not path.is_file():
            raise VerificationError(f"missing weight: {path}")
        md5, sha256, byte_size = _hash_file(path)
        if md5 != item["provider_md5"]:
            raise VerificationError(
                f"provider MD5 mismatch for {item['target']}: expected {item['provider_md5']}, got {md5}"
            )
        if sha256 != item["sha256"]:
            raise VerificationError(
                f"SHA-256 mismatch for {item['target']}: expected {item['sha256']}, got {sha256}"
            )
        if byte_size != item["byte_size"]:
            raise VerificationError(
                f"byte-size mismatch for {item['target']}: expected {item['byte_size']}, got {byte_size}"
            )
        results.append(
            {
                "target": item["target"],
                "filename": item["filename"],
                "provider_md5": md5,
                "sha256": sha256,
                "byte_size": byte_size,
            }
        )
    return {
        "status": "QUARANTINE_WEIGHTS_VERIFIED",
        "profile_id": data["profile_id"],
        "authority_transfer": False,
        "weights": results,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", required=True, type=Path)
    parser.add_argument("--profile", type=Path)
    parser.add_argument("--resource-receipt", type=Path)
    parser.add_argument("--runtime-review", type=Path)
    parser.add_argument("--weights-dir", type=Path)
    args = parser.parse_args(argv)

    try:
        data = _load_json(args.manifest)
        validate_manifest(data)
        if args.profile is not None:
            validate_frozen_profile(data, _load_json(args.profile))
        if args.resource_receipt is not None:
            validate_resource_receipt(data, _load_json(args.resource_receipt))
        if args.runtime_review is not None:
            validate_runtime_review(data, _load_json(args.runtime_review))
        weight_result = verify_weights(data, args.weights_dir) if args.weights_dir is not None else None
        result = {
            "status": "MODEL_PROFILE_LOCK_VALID",
            "profile_id": data["profile_id"],
            "profile_checksum": data["frozen_profile"]["profile_checksum"],
            "runtime_admission": False,
            "pilot_authorized": False,
            "authority_transfer": False,
        }
        if weight_result is not None:
            result["quarantine"] = weight_result
    except VerificationError as exc:
        print(json.dumps({"status": "FAILED", "error": str(exc)}, sort_keys=True))
        return 2

    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
