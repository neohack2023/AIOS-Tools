from __future__ import annotations

import hashlib
import json
import re
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

CLEAN_ROOM = {
    "memory": False,
    "custom_instructions": False,
    "plugins": False,
    "project_context": False,
    "prior_chat_context": False,
}
ALLOWED_PRODUCT_SURFACE_LANES = {
    "NONE",
    "CHATGPT_TEMPORARY_UNPERSONALIZED",
}


class PortablePackageEvalError(ValueError):
    """Raised when a portable-package evaluation contract is invalid."""


@dataclass(frozen=True)
class PortablePackageEvalCapsule:
    status: str
    output_dir: Path
    manifest_path: Path
    package_on_path: Path
    package_off_path: Path
    grader_path: Path
    product_surface_plan_path: Path
    package_sha256: str
    fixture_sha256: str


def _sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _sha256_file(path: Path) -> str:
    return _sha256_bytes(path.read_bytes())


def _canonical_json(value: object) -> bytes:
    return json.dumps(
        value, sort_keys=True, separators=(",", ":"), ensure_ascii=False
    ).encode("utf-8")


def _write_json(path: Path, value: object) -> None:
    path.write_text(
        json.dumps(value, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def _require_text(payload: dict[str, Any], field: str) -> str:
    value = payload.get(field)
    if not isinstance(value, str) or not value.strip():
        raise PortablePackageEvalError(f"{field} must be a non-empty string")
    return value.strip()


def _text_list(payload: dict[str, Any], field: str) -> list[str]:
    value = payload.get(field, [])
    if not isinstance(value, list) or any(
        not isinstance(item, str) or not item.strip() for item in value
    ):
        raise PortablePackageEvalError(f"{field} must be a list of non-empty strings")
    return [item.strip() for item in value]


def load_fixture(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise PortablePackageEvalError(f"cannot load fixture: {exc}") from exc
    if not isinstance(payload, dict):
        raise PortablePackageEvalError("fixture root must be an object")
    if payload.get("fixture_version") != "0.1":
        raise PortablePackageEvalError("fixture_version must be 0.1")
    _require_text(payload, "fixture_id")
    _require_text(payload, "task_prompt")
    _text_list(payload, "allowed_tools")
    _text_list(payload, "semantic_dimensions")

    assertions = payload.get("deterministic_assertions", {})
    if not isinstance(assertions, dict):
        raise PortablePackageEvalError("deterministic_assertions must be an object")
    for key in (
        "required_markers",
        "forbidden_markers",
        "ordered_markers",
        "required_regex",
    ):
        _text_list(assertions, key)
    max_chars = assertions.get("max_total_chars")
    if max_chars is not None and (
        not isinstance(max_chars, int) or isinstance(max_chars, bool) or max_chars < 1
    ):
        raise PortablePackageEvalError("max_total_chars must be a positive integer")

    product = payload.get("product_surface", {})
    if not isinstance(product, dict):
        raise PortablePackageEvalError("product_surface must be an object")
    required = product.get("required", False)
    if not isinstance(required, bool):
        raise PortablePackageEvalError("product_surface.required must be boolean")
    lane = product.get("lane", "NONE")
    if lane not in ALLOWED_PRODUCT_SURFACE_LANES:
        raise PortablePackageEvalError(f"unsupported product-surface lane: {lane}")
    takeover = product.get("human_takeover_allowed", False)
    if not isinstance(takeover, bool):
        raise PortablePackageEvalError(
            "product_surface.human_takeover_allowed must be boolean"
        )
    if required and lane == "NONE":
        raise PortablePackageEvalError(
            "required product-surface evaluation must declare a real lane"
        )
    return payload


def _request_payload(
    *,
    fixture: dict[str, Any],
    treatment: str,
    package_path: Path | None,
    package_sha256: str | None,
) -> dict[str, Any]:
    package_instruction = fixture.get(
        "package_entry_instruction",
        "Use only the attached portable package as package-specific working knowledge. "
        "Do not assume prior project knowledge.",
    )
    return {
        "request_schema_version": "0.1",
        "treatment": treatment,
        "clean_room": dict(CLEAN_ROOM),
        "task_prompt": fixture["task_prompt"],
        "allowed_tools": list(fixture.get("allowed_tools", [])),
        "research_policy": "EXPLICIT_ONLY",
        "package_attachment": (
            None
            if package_path is None
            else {
                "display_name": package_path.name,
                "sha256": package_sha256,
            }
        ),
        "package_entry_instruction": (
            None if package_path is None else package_instruction
        ),
        "provider": "CALLER_SUPPLIED",
        "model": "CALLER_SUPPLIED",
        "store": False,
    }


def build_eval_capsule(
    *,
    package_path: Path,
    fixture_path: Path,
    output_dir: Path,
) -> PortablePackageEvalCapsule:
    package_path = Path(package_path)
    fixture_path = Path(fixture_path)
    output_dir = Path(output_dir)

    if not package_path.is_file():
        raise PortablePackageEvalError("package_path must be an existing file")
    fixture = load_fixture(fixture_path)
    package_sha256 = _sha256_file(package_path)
    fixture_sha256 = _sha256_file(fixture_path)
    output_dir.mkdir(parents=True, exist_ok=True)

    on_request = _request_payload(
        fixture=fixture,
        treatment="PACKAGE_ON",
        package_path=package_path,
        package_sha256=package_sha256,
    )
    off_request = _request_payload(
        fixture=fixture,
        treatment="PACKAGE_OFF",
        package_path=None,
        package_sha256=None,
    )
    grader = {
        "grader_schema_version": "0.1",
        "fixture_id": fixture["fixture_id"],
        "deterministic_assertions": fixture.get("deterministic_assertions", {}),
        "semantic_dimensions": fixture.get("semantic_dimensions", []),
        "semantic_grade_status": "NOT_EXECUTED",
    }
    product = fixture.get("product_surface", {})
    product_plan = {
        "plan_schema_version": "0.1",
        "fixture_id": fixture["fixture_id"],
        "required": product.get("required", False),
        "lane": product.get("lane", "NONE"),
        "status": "NOT_EXECUTED",
        "temporary_chat": {
            "personalization": "UNPERSONALIZED",
            **CLEAN_ROOM,
        },
        "human_takeover": {
            "allowed": product.get("human_takeover_allowed", False),
            "secret_input_model_visible": False,
            "states": [
                "AUTH_REQUIRED",
                "USER_TAKEOVER",
                "VERIFY_PENDING",
                "AUTOMATION_RESUMED",
            ],
        },
    }
    package_on_path = output_dir / "package-on-request.json"
    package_off_path = output_dir / "package-off-request.json"
    grader_path = output_dir / "grader-contract.json"
    product_surface_plan_path = output_dir / "product-surface-plan.json"
    _write_json(package_on_path, on_request)
    _write_json(package_off_path, off_request)
    _write_json(grader_path, grader)
    _write_json(product_surface_plan_path, product_plan)

    invariant_fields = (
        "task_prompt",
        "allowed_tools",
        "research_policy",
        "provider",
        "model",
        "store",
    )
    if any(on_request[field] != off_request[field] for field in invariant_fields):
        raise PortablePackageEvalError("paired treatment invariants drifted")

    files = [
        package_on_path,
        package_off_path,
        grader_path,
        product_surface_plan_path,
    ]
    manifest = {
        "manifest_schema_version": "0.1",
        "fixture_id": fixture["fixture_id"],
        "fixture_sha256": fixture_sha256,
        "package": {
            "display_name": package_path.name,
            "sha256": package_sha256,
        },
        "run_classification": "PORTABLE_PACKAGE_REGRESSION",
        "pairing": {
            "treatments": ["PACKAGE_OFF", "PACKAGE_ON"],
            "invariant_fields": list(invariant_fields),
            "only_allowed_treatment_delta": "package_attachment_and_entry_instruction",
        },
        "clean_room": dict(CLEAN_ROOM),
        "score_status": "NOT_EXECUTED",
        "product_surface_status": "NOT_EXECUTED",
        "artifact_digests": {
            item.name: _sha256_file(item) for item in files
        },
    }
    manifest_path = output_dir / "eval-manifest.json"
    _write_json(manifest_path, manifest)

    return PortablePackageEvalCapsule(
        status="READY_TO_EXECUTE",
        output_dir=output_dir,
        manifest_path=manifest_path,
        package_on_path=package_on_path,
        package_off_path=package_off_path,
        grader_path=grader_path,
        product_surface_plan_path=product_surface_plan_path,
        package_sha256=package_sha256,
        fixture_sha256=fixture_sha256,
    )
def grade_output_text(
    *, output_text: str, grader_contract: dict[str, Any]
) -> dict[str, Any]:
    assertions = grader_contract.get("deterministic_assertions", {})
    if not isinstance(assertions, dict):
        raise PortablePackageEvalError("grader deterministic_assertions must be object")
    checks: list[dict[str, Any]] = []

    for marker in assertions.get("required_markers", []):
        checks.append({
            "kind": "required_marker",
            "value": marker,
            "passed": marker in output_text,
        })
    for marker in assertions.get("forbidden_markers", []):
        checks.append({
            "kind": "forbidden_marker",
            "value": marker,
            "passed": marker not in output_text,
        })
    ordered = assertions.get("ordered_markers", [])
    if ordered:
        positions = [output_text.find(marker) for marker in ordered]
        ordered_pass = all(pos >= 0 for pos in positions) and positions == sorted(positions)
        checks.append({
            "kind": "ordered_markers",
            "value": ordered,
            "passed": ordered_pass,
        })
    for pattern in assertions.get("required_regex", []):
        checks.append({
            "kind": "required_regex",
            "value": pattern,
            "passed": re.search(pattern, output_text, flags=re.MULTILINE) is not None,
        })
    max_chars = assertions.get("max_total_chars")
    if max_chars is not None:
        checks.append({
            "kind": "max_total_chars",
            "value": max_chars,
            "observed": len(output_text),
            "passed": len(output_text) <= max_chars,
        })

    passed = sum(1 for item in checks if item["passed"])
    return {
        "grade_schema_version": "0.1",
        "deterministic_status": "PASS" if passed == len(checks) else "FAIL",
        "passed_checks": passed,
        "total_checks": len(checks),
        "checks": checks,
        "output_sha256": _sha256_bytes(output_text.encode("utf-8")),
        "output_characters": len(output_text),
        "semantic_grade_status": "NOT_EXECUTED",
    }


def compare_grade_results(
    *, package_off: dict[str, Any], package_on: dict[str, Any]
) -> dict[str, Any]:
    for label, payload in (("PACKAGE_OFF", package_off), ("PACKAGE_ON", package_on)):
        if payload.get("grade_schema_version") != "0.1":
            raise PortablePackageEvalError(f"{label} grade schema must be 0.1")
    off_passed = int(package_off.get("passed_checks", 0))
    on_passed = int(package_on.get("passed_checks", 0))
    return {
        "comparison_schema_version": "0.1",
        "package_off_passed_checks": off_passed,
        "package_on_passed_checks": on_passed,
        "passed_check_delta": on_passed - off_passed,
        "package_off_status": package_off.get("deterministic_status"),
        "package_on_status": package_on.get("deterministic_status"),
        "semantic_comparison_status": "NOT_EXECUTED",
        "comparison_authoritative": False,
    }
