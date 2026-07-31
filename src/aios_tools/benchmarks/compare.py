from __future__ import annotations

import csv
import json
from pathlib import Path


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


def compare_score_artifacts(
    *,
    direct_path: Path,
    aios_path: Path,
    benchmark_source_ref: str,
    profile_sha256: str,
) -> dict[str, object]:
    direct = load_numeric_metrics(direct_path)
    aios = load_numeric_metrics(aios_path)
    shared = sorted(set(direct) & set(aios))
    if not shared:
        raise ScoreComparisonError(
            "score artifacts have no shared numeric metrics"
        )
    return {
        "comparison_schema_version": "0.1.0",
        "benchmark_id": "bfcl-v4",
        "benchmark_source_ref": benchmark_source_ref,
        "profile_sha256": profile_sha256,
        "direct_artifact": str(Path(direct_path)),
        "aios_artifact": str(Path(aios_path)),
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
