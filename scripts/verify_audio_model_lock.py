#!/usr/bin/env python3
"""Fail-closed verifier for the Slice 2A Open-Unmix model-lock manifest.

This tool performs no network access and does not mutate the manifest. It can
validate the candidate state without weight files or verify local quarantined
weights when --weights-dir is supplied.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from pathlib import Path
from typing import Any

EXPECTED_TARGETS = ["vocals", "drums", "bass", "other"]
HEX32 = re.compile(r"^[0-9a-f]{32}$")
HEX64 = re.compile(r"^[0-9a-f]{64}$")


class VerificationError(ValueError):
    """Raised when the model-lock evidence fails closed."""


def _load_json(path: Path) -> dict[str, Any]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise VerificationError(f"manifest not found: {path}") from exc
    except json.JSONDecodeError as exc:
        raise VerificationError(f"invalid JSON: {exc}") from exc
    if not isinstance(data, dict):
        raise VerificationError("manifest root must be an object")
    return data


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


def validate_manifest(data: dict[str, Any]) -> None:
    if data.get("schema_version") != "0.1.0":
        raise VerificationError("unsupported schema_version")
    if data.get("profile_id") != "slice2-stem-section-v0.1":
        raise VerificationError("unexpected profile_id")
    if data.get("tool_identity") != "audio.stem_section_analyze":
        raise VerificationError("unexpected tool_identity")

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
    if profile.get("overwrite_source_or_slice1") is not False:
        raise VerificationError("source and Slice 1 overwrite must be disabled")

    weights = data.get("weights")
    if not isinstance(weights, list) or len(weights) != 4:
        raise VerificationError("exactly four weight entries are required")
    if [item.get("target") for item in weights] != EXPECTED_TARGETS:
        raise VerificationError("weight target order mismatch")
    filenames = [item.get("filename") for item in weights]
    if len(set(filenames)) != 4 or not all(isinstance(name, str) and name for name in filenames):
        raise VerificationError("weight filenames must be unique non-empty strings")
    for item in weights:
        md5 = item.get("provider_md5")
        if not isinstance(md5, str) or not HEX32.fullmatch(md5):
            raise VerificationError(f"invalid provider_md5 for {item.get('target')}")
        sha256 = item.get("sha256")
        if sha256 is not None and (not isinstance(sha256, str) or not HEX64.fullmatch(sha256)):
            raise VerificationError(f"invalid sha256 for {item.get('target')}")
        if item.get("admitted") is True and (sha256 is None or item.get("byte_size") is None):
            raise VerificationError(f"admitted weight lacks SHA-256 or byte size: {item.get('target')}")

    gates = data.get("gates")
    if not isinstance(gates, dict):
        raise VerificationError("gates must be an object")
    all_locked = all(item.get("sha256") and item.get("byte_size") for item in weights)
    if bool(gates.get("all_weight_sha256_present")) != bool(all_locked):
        raise VerificationError("all_weight_sha256_present does not match weight entries")
    if gates.get("runtime_admission") is True and not all_locked:
        raise VerificationError("runtime admission is forbidden before all weights are locked")
    if gates.get("pilot_authorized") is True and gates.get("runtime_admission") is not True:
        raise VerificationError("pilot authorization requires runtime admission")


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
        expected_sha256 = item.get("sha256")
        if expected_sha256 is not None and sha256 != expected_sha256:
            raise VerificationError(
                f"SHA-256 mismatch for {item['target']}: expected {expected_sha256}, got {sha256}"
            )
        expected_size = item.get("byte_size")
        if expected_size is not None and byte_size != expected_size:
            raise VerificationError(
                f"byte-size mismatch for {item['target']}: expected {expected_size}, got {byte_size}"
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
    parser.add_argument("--weights-dir", type=Path)
    args = parser.parse_args(argv)

    try:
        data = _load_json(args.manifest)
        validate_manifest(data)
        if args.weights_dir is None:
            result = {
                "status": "CANDIDATE_MANIFEST_VALID",
                "profile_id": data["profile_id"],
                "runtime_admission": data["gates"]["runtime_admission"],
                "pilot_authorized": data["gates"]["pilot_authorized"],
                "authority_transfer": False,
            }
        else:
            result = verify_weights(data, args.weights_dir)
    except VerificationError as exc:
        print(json.dumps({"status": "FAILED", "error": str(exc)}, sort_keys=True))
        return 2

    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
