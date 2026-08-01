from __future__ import annotations

import ast
import hashlib
import json
import os
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Mapping, Sequence

from .subjects import SubjectRegistry, load_subject_registry

BFCL_PIN = "6ea57973c7a6097fd7c5915698c54c17c5b1b6c8"
DEFAULT_CATEGORIES = ("simple", "parallel", "multiple")
RESOURCE_CLASS = "CPU_OR_REMOTE_MODEL"
RUN_CLASSIFICATION = "PROTOCOL_ADAPTED_SMOKE_RUN"
EVALUATION_SCOPE = "OFFICIAL_PARTIAL_EVALUATION"


class BFCLPackageError(ValueError):
    """Raised when a BFCL A/B execution package cannot be constructed."""


@dataclass(frozen=True)
class BFCLPackage:
    output_dir: Path
    manifest_path: Path
    commands_path: Path
    direct_manifest_path: Path
    aios_manifest_path: Path
    status: str
    score_status: str
    direct_model_key: str | None
    aios_model_key: str | None
    profile_sha256: str
    categories: tuple[str, ...]
    case_shard_status: str


def ensure_categories(categories: Sequence[str]) -> tuple[str, ...]:
    normalized: list[str] = []
    for category in categories:
        value = str(category).strip()
        if not value:
            raise BFCLPackageError("category values must be non-empty")
        if value not in normalized:
            normalized.append(value)
    if not normalized:
        raise BFCLPackageError("at least one BFCL category is required")
    return tuple(normalized)


def load_case_map(
    path: Path | None,
    categories: tuple[str, ...],
) -> tuple[dict[str, list[str]], str]:
    if path is None:
        return {category: [] for category in categories}, "UNRESOLVED"
    try:
        payload = json.loads(Path(path).read_text())
    except (OSError, json.JSONDecodeError) as exc:
        raise BFCLPackageError(f"cannot load BFCL case map: {exc}") from exc
    if not isinstance(payload, dict):
        raise BFCLPackageError("BFCL case map root must be an object")
    result: dict[str, list[str]] = {}
    for category in categories:
        ids = payload.get(category)
        if not isinstance(ids, list) or not ids:
            raise BFCLPackageError(
                f"case map must include at least one id for {category}"
            )
        normalized: list[str] = []
        for case_id in ids:
            if not isinstance(case_id, str) or not case_id.strip():
                raise BFCLPackageError(f"{category} contains an invalid case id")
            value = case_id.strip()
            if value not in normalized:
                normalized.append(value)
        result[category] = normalized
    extra = sorted(set(payload) - set(categories))
    if extra:
        raise BFCLPackageError(
            f"case map contains unrequested categories: {extra}"
        )
    return result, "RESOLVED"


def _canonical_json_bytes(payload: object) -> bytes:
    return json.dumps(
        payload,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    ).encode()


def _canonical_sha256(payload: object) -> str:
    return hashlib.sha256(_canonical_json_bytes(payload)).hexdigest()


def _file_sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _git_output(root: Path, *args: str) -> str:
    completed = subprocess.run(
        ["git", "-C", str(root), *args],
        check=False,
        capture_output=True,
        text=True,
    )
    if completed.returncode != 0:
        detail = completed.stderr.strip() or completed.stdout.strip()
        raise BFCLPackageError(f"git {' '.join(args)} failed: {detail}")
    return completed.stdout.strip()


def _model_handlers_from_source(path: Path) -> dict[str, str]:
    try:
        tree = ast.parse(path.read_text())
    except (OSError, SyntaxError) as exc:
        raise BFCLPackageError(f"cannot parse pinned BFCL model registry: {exc}") from exc
    result: dict[str, str] = {}
    for node in tree.body:
        if not isinstance(node, ast.Assign) or not isinstance(node.value, ast.Dict):
            continue
        target_names = [target.id for target in node.targets if isinstance(target, ast.Name)]
        if not any(name.endswith("_model_map") for name in target_names):
            continue
        for key_node, value_node in zip(node.value.keys, node.value.values):
            if not (
                isinstance(key_node, ast.Constant)
                and isinstance(key_node.value, str)
                and isinstance(value_node, ast.Call)
            ):
                continue
            handler_name: str | None = None
            for keyword in value_node.keywords:
                if keyword.arg != "model_handler":
                    continue
                if isinstance(keyword.value, ast.Name):
                    handler_name = keyword.value.id
                elif isinstance(keyword.value, ast.Attribute):
                    handler_name = keyword.value.attr
            if handler_name:
                result[key_node.value] = handler_name
    return result


def inspect_bfcl_checkout(
    *,
    bfcl_root: Path | None,
    model_key: str | None,
) -> dict[str, object]:
    result: dict[str, object] = {
        "bfcl_root": str(Path(bfcl_root).resolve()) if bfcl_root else None,
        "checkout_present": False,
        "observed_pin": None,
        "pin_valid": False,
        "worktree_clean": False,
        "model_supported": False,
        "model_handler": None,
        "model_handler_supported": False,
        "validation_error": None,
    }
    if bfcl_root is None:
        result["validation_error"] = "BFCL_ROOT is not set"
        return result
    root = Path(bfcl_root).resolve()
    if not root.is_dir() or not (root / ".git").exists():
        result["validation_error"] = "BFCL_ROOT is not a Git checkout"
        return result
    result["checkout_present"] = True
    try:
        observed_pin = _git_output(root, "rev-parse", "HEAD")
        result["observed_pin"] = observed_pin
        result["pin_valid"] = observed_pin == BFCL_PIN
        status = _git_output(root, "status", "--porcelain=v1", "--untracked-files=all")
        result["worktree_clean"] = status == ""
        config_path = (
            root
            / "berkeley-function-call-leaderboard"
            / "bfcl_eval"
            / "constants"
            / "model_config.py"
        )
        handlers = _model_handlers_from_source(config_path)
        handler_name = handlers.get(model_key or "")
        result["model_handler"] = handler_name
        result["model_supported"] = handler_name is not None
        result["model_handler_supported"] = handler_name == "OpenAIResponsesHandler"
    except BFCLPackageError as exc:
        result["validation_error"] = str(exc)
    if not result["pin_valid"] and result["validation_error"] is None:
        result["validation_error"] = "BFCL checkout is not at the pinned commit"
    elif not result["worktree_clean"] and result["validation_error"] is None:
        result["validation_error"] = "BFCL checkout has modified or untracked files"
    elif not result["model_supported"] and result["validation_error"] is None:
        result["validation_error"] = "configured model key is absent from pinned BFCL"
    elif not result["model_handler_supported"] and result["validation_error"] is None:
        result["validation_error"] = (
            "configured model is not backed by OpenAIResponsesHandler"
        )
    result["execution_model_valid"] = all(
        bool(result[field])
        for field in (
            "checkout_present",
            "pin_valid",
            "worktree_clean",
            "model_supported",
            "model_handler_supported",
        )
    )
    return result


def _write_json(path: Path, payload: object) -> None:
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n")


def _render_handler(profile_text: str, profile_sha256: str) -> str:
    return f'''from __future__ import annotations

import copy
import hashlib

from bfcl_eval.model_handler.api_inference.openai_response import OpenAIResponsesHandler

PROFILE_ID = "AIOS-OPERATOR-001-BFCL-v0.1"
PROFILE_SHA256 = "{profile_sha256}"
PROFILE_TEXT = {profile_text!r}

if hashlib.sha256(PROFILE_TEXT.encode()).hexdigest() != PROFILE_SHA256:
    raise RuntimeError("embedded AIOS BFCL profile hash mismatch")


class AIOSOpenAIResponsesHandler(OpenAIResponsesHandler):
    """BFCL OpenAI Responses handler with the versioned AIOS routing profile."""

    def add_first_turn_message_FC(
        self,
        inference_data: dict,
        first_turn_message: list[dict],
    ) -> dict:
        prepared = copy.deepcopy(first_turn_message)
        prepared.insert(
            0,
            {{"role": "developer", "content": PROFILE_TEXT}},
        )
        return super().add_first_turn_message_FC(inference_data, prepared)
'''


def _render_sitecustomize() -> str:
    return '''from __future__ import annotations

import os
from dataclasses import replace

import bfcl_eval.constants.model_config as model_config
from bfcl_eval.constants.supported_models import SUPPORTED_MODELS
from aios_bfcl_handler import AIOSOpenAIResponsesHandler

base_key = os.environ.get("AIOS_BFCL_BASE_MODEL_KEY", "").strip()
treatment_key = os.environ.get("AIOS_BFCL_TREATMENT_MODEL_KEY", "").strip()

if not base_key or not treatment_key:
    raise RuntimeError(
        "AIOS_BFCL_BASE_MODEL_KEY and AIOS_BFCL_TREATMENT_MODEL_KEY are required"
    )

mapping = model_config.MODEL_CONFIG_MAPPING
if base_key not in mapping:
    raise RuntimeError(f"unknown BFCL base model key: {base_key}")

base = mapping[base_key]
if base.model_handler.__name__ != "OpenAIResponsesHandler":
    raise RuntimeError(
        "AIOS BFCL v0.1 only supports BFCL models backed by OpenAIResponsesHandler"
    )

treatment = replace(
    base,
    display_name=f"AIOS {base.display_name}",
    model_handler=AIOSOpenAIResponsesHandler,
)
mapping[treatment_key] = treatment

api_mapping = getattr(model_config, "api_inference_model_map", None)
if isinstance(api_mapping, dict):
    api_mapping[treatment_key] = treatment

if treatment_key not in SUPPORTED_MODELS:
    SUPPORTED_MODELS.append(treatment_key)
'''


def _render_selector(categories: tuple[str, ...], per_category: int) -> str:
    categories_literal = repr(list(categories))
    return f'''from __future__ import annotations

import json
from pathlib import Path

from bfcl_eval.utils import load_dataset_entry

CATEGORIES = {categories_literal}
PER_CATEGORY = {per_category}

selected = {{}}
for category in CATEGORIES:
    ids = sorted(entry["id"] for entry in load_dataset_entry(category))
    if len(ids) < PER_CATEGORY:
        raise RuntimeError(
            f"{{category}} has {{len(ids)}} entries, fewer than requested {{PER_CATEGORY}}"
        )
    selected[category] = ids[:PER_CATEGORY]

output_path = Path("selected-case-map.json")
output_path.write_text(json.dumps(selected, indent=2, sort_keys=True) + "\\n")
print(json.dumps(selected, indent=2, sort_keys=True))
'''


def _render_commands(
    *,
    categories: tuple[str, ...],
    case_shard_status: str,
) -> str:
    categories_csv = ",".join(categories)
    case_gate = (
        '''cp "$PACKAGE_DIR/test_case_ids_to_generate.json" \\
  "$DIRECT_ROOT/test_case_ids_to_generate.json"
cp "$PACKAGE_DIR/test_case_ids_to_generate.json" \\
  "$AIOS_ROOT/test_case_ids_to_generate.json"'''
        if case_shard_status == "RESOLVED"
        else '''echo "BLOCKED: resolve the BFCL case shard first." >&2
echo "Run select_case_shard.py inside the pinned BFCL environment, then regenerate this package with --case-map." >&2
exit 4'''
    )
    return f'''#!/usr/bin/env bash
set -euo pipefail

: "${{BFCL_ROOT:?Set BFCL_ROOT to the pinned gorilla repository root}}"
: "${{OPENAI_API_KEY:?OPENAI_API_KEY is required by BFCL but must not be written to artifacts}}"
: "${{AIOS_BENCH_BFCL_MODEL:?Set AIOS_BENCH_BFCL_MODEL to a supported pinned-BFCL model key}}"
: "${{AIOS_BENCH_ACK_RESOURCE:?Set AIOS_BENCH_ACK_RESOURCE=bfcl-v4 to acknowledge model-credit and CPU use}}"

test "$AIOS_BENCH_ACK_RESOURCE" = "bfcl-v4"

PACKAGE_DIR="$(cd "$(dirname "${{BASH_SOURCE[0]}}")" && pwd)"
BFCL_PROJECT="$BFCL_ROOT/berkeley-function-call-leaderboard"
DIRECT_ROOT="$PACKAGE_DIR/runs/direct"
AIOS_ROOT="$PACKAGE_DIR/runs/aios"
DIRECT_MODEL_KEY="$AIOS_BENCH_BFCL_MODEL"
AIOS_MODEL_KEY="aios::$AIOS_BENCH_BFCL_MODEL"
CATEGORIES="{categories_csv}"

verify_package_integrity() {{
  python - "$PACKAGE_DIR/run-manifest.json" <<'PY_VERIFY'
import hashlib
import json
import sys
from pathlib import Path

manifest_path = Path(sys.argv[1]).resolve()
package_root = manifest_path.parent
manifest = json.loads(manifest_path.read_text())
digests = manifest.get("package_file_digests")
if not isinstance(digests, dict) or not digests:
    raise SystemExit("package manifest has no file digests")
for relative, expected in sorted(digests.items()):
    path = (package_root / relative).resolve()
    if package_root != path and package_root not in path.parents:
        raise SystemExit(f"package path escapes root: {{relative}}")
    if not path.is_file():
        raise SystemExit(f"package file is missing: {{relative}}")
    observed = hashlib.sha256(path.read_bytes()).hexdigest()
    if observed != expected:
        raise SystemExit(f"package digest mismatch: {{relative}}")
PY_VERIFY
}}

verify_bfcl_checkout() {{
  observed_pin="$(git -C "$BFCL_ROOT" rev-parse HEAD)"
  test "$observed_pin" = "{BFCL_PIN}"
  if test -n "$(git -C "$BFCL_ROOT" status --porcelain=v1 --untracked-files=all)"; then
    echo "pinned BFCL checkout is modified or contains untracked files" >&2
    exit 5
  fi
  cd "$BFCL_PROJECT"
  if ! bfcl models | grep -Fqx "$DIRECT_MODEL_KEY"; then
    echo "unsupported BFCL model key at pinned commit: $DIRECT_MODEL_KEY" >&2
    exit 3
  fi
}}

verify_package_integrity
verify_bfcl_checkout
mkdir -p "$DIRECT_ROOT" "$AIOS_ROOT"
{case_gate}

run_direct() {{
  unset AIOS_BFCL_BASE_MODEL_KEY AIOS_BFCL_TREATMENT_MODEL_KEY
  export BFCL_PROJECT_ROOT="$DIRECT_ROOT"
  cd "$BFCL_PROJECT"
  bfcl generate \\
    --model "$DIRECT_MODEL_KEY" \\
    --test-category "" \\
    --run-ids \\
    --result-dir result
  bfcl evaluate \\
    --model "$DIRECT_MODEL_KEY" \\
    --test-category "$CATEGORIES" \\
    --result-dir result \\
    --score-dir score \\
    --partial-eval
}}

run_aios() {{
  export BFCL_PROJECT_ROOT="$AIOS_ROOT"
  export AIOS_BFCL_BASE_MODEL_KEY="$DIRECT_MODEL_KEY"
  export AIOS_BFCL_TREATMENT_MODEL_KEY="$AIOS_MODEL_KEY"
  export PYTHONPATH="$PACKAGE_DIR/overlay${{PYTHONPATH:+:$PYTHONPATH}}"
  cd "$BFCL_PROJECT"
  bfcl generate \\
    --model "$AIOS_MODEL_KEY" \\
    --test-category "" \\
    --run-ids \\
    --result-dir result
  bfcl evaluate \\
    --model "$AIOS_MODEL_KEY" \\
    --test-category "$CATEGORIES" \\
    --result-dir result \\
    --score-dir score \\
    --partial-eval
}}

case "${{1:-}}" in
  direct) run_direct ;;
  aios) run_aios ;;
  pair) run_direct; run_aios ;;
  *)
    echo "usage: $0 direct|aios|pair" >&2
    exit 2
    ;;
esac
'''


def _subject_run_manifest(
    *,
    package_id: str,
    subject_id: str,
    treatment: str,
    model_key: str | None,
    base_model_key: str | None,
    case_map: dict[str, list[str]],
    case_map_sha256: str,
    categories: tuple[str, ...],
    profile_id: str | None,
    profile_sha256: str | None,
) -> dict[str, object]:
    return {
        "run_manifest_schema_version": "0.1.0",
        "package_id": package_id,
        "benchmark_id": "bfcl-v4",
        "benchmark_source_ref": BFCL_PIN,
        "run_classification": RUN_CLASSIFICATION,
        "evaluation_scope": EVALUATION_SCOPE,
        "official_score_claim_allowed": False,
        "subject_id": subject_id,
        "treatment": treatment,
        "base_model_key": base_model_key,
        "model_key": model_key,
        "case_map_sha256": case_map_sha256,
        "case_map": case_map,
        "categories": list(categories),
        "generation_settings": {
            "temperature": 0.001,
            "run_ids": True,
            "partial_eval": True,
            "store": False,
        },
        "evaluator": {
            "name": "BFCL V4 native evaluator",
            "source_ref": BFCL_PIN,
            "mode": "partial-eval",
        },
        "resource_class": RESOURCE_CLASS,
        "profile_id": profile_id,
        "profile_sha256": profile_sha256,
        "raw_artifacts_authoritative": True,
        "score_status": "NOT_EXECUTED",
    }


def create_bfcl_ab_package(
    *,
    registry_path: Path,
    output_dir: Path,
    categories: Sequence[str] = DEFAULT_CATEGORIES,
    per_category: int = 1,
    case_map_path: Path | None = None,
    environ: Mapping[str, str] | None = None,
    resource_acknowledged: bool = False,
) -> BFCLPackage:
    if per_category < 1:
        raise BFCLPackageError("per_category must be at least 1")
    environment = os.environ if environ is None else environ
    registry: SubjectRegistry = load_subject_registry(registry_path)
    direct, aios = registry.pair_for("bfcl-v4")
    normalized_categories = ensure_categories(categories)
    case_map, case_shard_status = load_case_map(case_map_path, normalized_categories)
    model_key = environment.get(direct.model_env, "").strip()
    direct_model_key = model_key or None
    aios_model_key = f"aios::{model_key}" if model_key else None
    bfcl_root_value = environment.get("BFCL_ROOT", "").strip()
    model_validation = inspect_bfcl_checkout(
        bfcl_root=Path(bfcl_root_value) if bfcl_root_value else None,
        model_key=direct_model_key,
    )

    profile_path = aios.resolve_profile_path(registry.repository_root)
    assert profile_path is not None
    profile_text = profile_path.read_text()
    assert aios.profile_sha256 is not None

    output_dir = Path(output_dir).resolve()
    if output_dir.exists() and any(output_dir.iterdir()):
        raise BFCLPackageError(f"output directory is not empty: {output_dir}")
    output_dir.mkdir(parents=True, exist_ok=True)
    overlay = output_dir / "overlay"
    overlay.mkdir()
    profile_dir = output_dir / "profile"
    profile_dir.mkdir()
    manifests_dir = output_dir / "manifests"
    manifests_dir.mkdir()

    handler_path = overlay / "aios_bfcl_handler.py"
    handler_path.write_text(_render_handler(profile_text, aios.profile_sha256))
    sitecustomize_path = overlay / "sitecustomize.py"
    sitecustomize_path.write_text(_render_sitecustomize())
    selector_path = output_dir / "select_case_shard.py"
    selector_path.write_text(_render_selector(normalized_categories, per_category))
    case_map_output = output_dir / "test_case_ids_to_generate.json"
    _write_json(case_map_output, case_map)
    packaged_profile_path = profile_dir / "aios-master-operator-bfcl.v0.1.txt"
    packaged_profile_path.write_text(profile_text)

    direct_admission = direct.admission(
        repository_root=registry.repository_root,
        environ=environment,
        resource_acknowledged=resource_acknowledged,
        case_shard_resolved=case_shard_status == "RESOLVED",
        model_validation=model_validation,
    )
    aios_admission = aios.admission(
        repository_root=registry.repository_root,
        environ=environment,
        resource_acknowledged=resource_acknowledged,
        case_shard_resolved=case_shard_status == "RESOLVED",
        model_validation=model_validation,
    )
    execution_ready = bool(
        direct_admission["execution_admission_ready"]
    ) and bool(aios_admission["execution_admission_ready"])

    case_map_sha256 = _canonical_sha256(case_map)
    package_identity = {
        "benchmark_source_ref": BFCL_PIN,
        "base_model_key": direct_model_key,
        "case_map_sha256": case_map_sha256,
        "categories": list(normalized_categories),
        "profile_sha256": aios.profile_sha256,
        "generation_settings": {
            "temperature": 0.001,
            "run_ids": True,
            "partial_eval": True,
            "store": False,
        },
    }
    package_id = _canonical_sha256(package_identity)
    direct_manifest_path = manifests_dir / "direct-run-manifest.json"
    aios_manifest_path = manifests_dir / "aios-run-manifest.json"
    _write_json(
        direct_manifest_path,
        _subject_run_manifest(
            package_id=package_id,
            subject_id=direct.id,
            treatment="DIRECT",
            model_key=direct_model_key,
            base_model_key=direct_model_key,
            case_map=case_map,
            case_map_sha256=case_map_sha256,
            categories=normalized_categories,
            profile_id=None,
            profile_sha256=None,
        ),
    )
    _write_json(
        aios_manifest_path,
        _subject_run_manifest(
            package_id=package_id,
            subject_id=aios.id,
            treatment="AIOS",
            model_key=aios_model_key,
            base_model_key=direct_model_key,
            case_map=case_map,
            case_map_sha256=case_map_sha256,
            categories=normalized_categories,
            profile_id=aios.profile_id,
            profile_sha256=aios.profile_sha256,
        ),
    )

    commands_path = output_dir / "run-bfcl-pair.sh"
    commands_path.write_text(
        _render_commands(
            categories=normalized_categories,
            case_shard_status=case_shard_status,
        )
    )
    commands_path.chmod(0o755)

    execution_files = {
        "overlay/aios_bfcl_handler.py": handler_path,
        "overlay/sitecustomize.py": sitecustomize_path,
        "select_case_shard.py": selector_path,
        "test_case_ids_to_generate.json": case_map_output,
        "profile/aios-master-operator-bfcl.v0.1.txt": packaged_profile_path,
        "manifests/direct-run-manifest.json": direct_manifest_path,
        "manifests/aios-run-manifest.json": aios_manifest_path,
        "run-bfcl-pair.sh": commands_path,
    }
    package_file_digests = {
        relative: _file_sha256(path) for relative, path in execution_files.items()
    }
    manifest = {
        "package_schema_version": "0.1.0",
        "package_id": package_id,
        "benchmark_id": "bfcl-v4",
        "benchmark_source_ref": BFCL_PIN,
        "run_classification": RUN_CLASSIFICATION,
        "evaluation_scope": EVALUATION_SCOPE,
        "official_score_claim_allowed": False,
        "paired_subjects": [direct.id, aios.id],
        "direct_model_key": direct_model_key,
        "aios_model_key": aios_model_key,
        "runtime_model_env": direct.model_env,
        "categories": list(normalized_categories),
        "per_category": per_category,
        "case_shard_status": case_shard_status,
        "case_map": case_map,
        "case_map_sha256": case_map_sha256,
        "profile_id": aios.profile_id,
        "profile_sha256": aios.profile_sha256,
        "resource_class": RESOURCE_CLASS,
        "resource_acknowledged": resource_acknowledged,
        "runtime_resource_ack_env": "AIOS_BENCH_ACK_RESOURCE",
        "model_validation": model_validation,
        "subject_admission": [direct_admission, aios_admission],
        "direct_run_manifest": str(direct_manifest_path.relative_to(output_dir)),
        "aios_run_manifest": str(aios_manifest_path.relative_to(output_dir)),
        "package_file_digests": package_file_digests,
        "execution_status": "READY_TO_EXECUTE" if execution_ready else "BLOCKED",
        "score_status": "NOT_EXECUTED",
        "raw_artifacts_authoritative": True,
        "normalized_comparison_authoritative": False,
        "forbidden_claims": [
            "full BFCL leaderboard score from a partial shard",
            "live AIOS retrieval or memory performance",
            "score inferred from readiness metadata",
        ],
    }
    manifest_path = output_dir / "run-manifest.json"
    _write_json(manifest_path, manifest)
    return BFCLPackage(
        output_dir=output_dir,
        manifest_path=manifest_path,
        commands_path=commands_path,
        direct_manifest_path=direct_manifest_path,
        aios_manifest_path=aios_manifest_path,
        status=str(manifest["execution_status"]),
        score_status="NOT_EXECUTED",
        direct_model_key=direct_model_key,
        aios_model_key=aios_model_key,
        profile_sha256=aios.profile_sha256,
        categories=normalized_categories,
        case_shard_status=case_shard_status,
    )
