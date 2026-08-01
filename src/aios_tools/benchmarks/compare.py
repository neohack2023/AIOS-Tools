from __future__ import annotations

import csv
import hashlib
import json
from pathlib import Path

RUN_CLASSIFICATION = "PROTOCOL_ADAPTED_SMOKE_RUN"
PAIR_INVARIANT_FIELDS = (
    "package_id",
    "benchmark_id",
    "benchmark_source_ref",
    "run_classification",
    "evaluation_scope",
    "official_score_claim_allowed",
    "base_model_key",
    "case_map_sha256",
    "categories",
    "generation_settings",
    "evaluator",
    "resource_class",
)


class ScoreComparisonError(ValueError):
    """Raised when BFCL score artifacts cannot be compared safely."""


def _flatten_numeric(value: object, *, prefix: str = "") -> dict[str, float]:
    result: dict[str, float] = {}
    if isinstance(value, bool):
        return result
    if isinstance(value, (int, float)):
        result[prefix or "value"] = float(value)
        return result
    if isinstance(value, dict):
        for key, child in value.items():
            child_prefix = f"{prefix}.{key}" if prefix else str(key)
            result.update(_flatten_numeric(child, prefix=child_prefix))
    return result


def _file_sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load_numeric_metrics(path: Path) -> dict[str, float]:
    path = Path(path)
    if not path.is_file():
        raise ScoreComparisonError(f"score artifact not found: {path}")
    if path.suffix.lower() == ".json":
        try:
            payload = json.loads(path.read_text())
        except json.JSONDecodeError as exc:
            raise ScoreComparisonError(
                f"invalid JSON score artifact: {path}"
            ) from exc
        metrics = _flatten_numeric(payload)
    elif path.suffix.lower() == ".csv":
        with path.open(newline="") as handle:
            rows = list(csv.DictReader(handle))
        if len(rows) != 1:
            raise ScoreComparisonError(
                "CSV score artifacts must contain exactly one data row"
            )
        metrics = {}
        for key, raw in rows[0].items():
            try:
                metrics[key] = float(raw)
            except (TypeError, ValueError):
                continue
    else:
        raise ScoreComparisonError("score artifact must be JSON or CSV")
    if not metrics:
        raise ScoreComparisonError(f"no numeric metrics found in {path}")
    return metrics


def _load_manifest(path: Path) -> dict[str, object]:
    path = Path(path)
    if not path.is_file():
        raise ScoreComparisonError(f"run manifest not found: {path}")
    try:
        payload = json.loads(path.read_text())
    except json.JSONDecodeError as exc:
        raise ScoreComparisonError(f"invalid JSON run manifest: {path}") from exc
    if not isinstance(payload, dict):
        raise ScoreComparisonError(f"run manifest root must be an object: {path}")
    return payload


def validate_paired_manifests(
    *,
    direct_manifest_path: Path,
    aios_manifest_path: Path,
) -> tuple[dict[str, object], dict[str, object]]:
    direct = _load_manifest(direct_manifest_path)
    aios = _load_manifest(aios_manifest_path)
    if direct.get("treatment") != "DIRECT":
        raise ScoreComparisonError("direct manifest treatment must be DIRECT")
    if aios.get("treatment") != "AIOS":
        raise ScoreComparisonError("AIOS manifest treatment must be AIOS")
    mismatches = [
        field
        for field in PAIR_INVARIANT_FIELDS
        if direct.get(field) != aios.get(field)
    ]
    if mismatches:
        raise ScoreComparisonError(
            "paired run manifests differ: " + ", ".join(mismatches)
        )
    if direct.get("run_classification") != RUN_CLASSIFICATION:
        raise ScoreComparisonError(
            "bounded BFCL shard must be PROTOCOL_ADAPTED_SMOKE_RUN"
        )
    if direct.get("official_score_claim_allowed") is not False:
        raise ScoreComparisonError(
            "partial BFCL comparison cannot allow an official score claim"
        )
    base_model_key = direct.get("base_model_key")
    if not isinstance(base_model_key, str) or not base_model_key:
        raise ScoreComparisonError("paired manifests require a base_model_key")
    if direct.get("model_key") != base_model_key:
        raise ScoreComparisonError("DIRECT model key must equal the base model key")
    if aios.get("model_key") != f"aios::{base_model_key}":
        raise ScoreComparisonError(
            "AIOS model key must be derived from the base model key"
        )
    if direct.get("profile_id") is not None or direct.get("profile_sha256") is not None:
        raise ScoreComparisonError("DIRECT manifest may not declare an AIOS profile")
    profile_sha256 = aios.get("profile_sha256")
    if not (
        isinstance(profile_sha256, str)
        and len(profile_sha256) == 64
        and all(ch in "0123456789abcdef" for ch in profile_sha256)
    ):
        raise ScoreComparisonError(
            "AIOS manifest requires a lowercase SHA-256 profile digest"
        )
    if not isinstance(aios.get("profile_id"), str) or not aios.get("profile_id"):
        raise ScoreComparisonError("AIOS manifest requires a profile_id")
    case_map_sha256 = direct.get("case_map_sha256")
    if not (
        isinstance(case_map_sha256, str)
        and len(case_map_sha256) == 64
        and all(ch in "0123456789abcdef" for ch in case_map_sha256)
    ):
        raise ScoreComparisonError(
            "paired manifests require a valid case-map digest"
        )
    return direct, aios


def compare_score_artifacts(
    *,
    direct_path: Path,
    aios_path: Path,
    direct_manifest_path: Path,
    aios_manifest_path: Path,
) -> dict[str, object]:
    direct_manifest, aios_manifest = validate_paired_manifests(
        direct_manifest_path=direct_manifest_path,
        aios_manifest_path=aios_manifest_path,
    )
    direct = load_numeric_metrics(direct_path)
    aios = load_numeric_metrics(aios_path)
    shared = sorted(set(direct) & set(aios))
    if not shared:
        raise ScoreComparisonError(
            "score artifacts have no shared numeric metrics"
        )
    return {
        "comparison_schema_version": "0.2.0",
        "package_id": direct_manifest["package_id"],
        "benchmark_id": direct_manifest["benchmark_id"],
        "benchmark_source_ref": direct_manifest["benchmark_source_ref"],
        "run_classification": direct_manifest["run_classification"],
        "evaluation_scope": direct_manifest["evaluation_scope"],
        "official_score_claim_allowed": False,
        "base_model_key": direct_manifest["base_model_key"],
        "case_map_sha256": direct_manifest["case_map_sha256"],
        "profile_sha256": aios_manifest["profile_sha256"],
        "direct_manifest": str(Path(direct_manifest_path)),
        "aios_manifest": str(Path(aios_manifest_path)),
        "direct_artifact": str(Path(direct_path)),
        "direct_artifact_sha256": _file_sha256(Path(direct_path)),
        "aios_artifact": str(Path(aios_path)),
        "aios_artifact_sha256": _file_sha256(Path(aios_path)),
        "metrics": [
            {
                "metric": key,
                "direct": direct[key],
                "aios": aios[key],
                "delta": aios[key] - direct[key],
            }
            for key in shared
        ],
        "raw_artifacts_authoritative": True,
        "comparison_authoritative": False,
    }
