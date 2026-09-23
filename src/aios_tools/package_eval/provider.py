from __future__ import annotations

import hashlib
import json
import urllib.error
import urllib.request
import uuid
from pathlib import Path
from typing import Any, Callable

from .context import compile_package_context
from .runtime import (
    PortablePackageEvalError,
    compare_grade_results,
    grade_output_text,
)

DEFAULT_RESPONSES_ENDPOINT = "https://api.openai.com/v1/responses"
SUPPORTED_TOOLS = frozenset({"web_search"})


class _NoRedirectHandler(urllib.request.HTTPRedirectHandler):
    """Fail closed instead of forwarding bearer credentials across redirects."""

    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def _validate_openai_endpoint(endpoint: str) -> str:
    if endpoint != DEFAULT_RESPONSES_ENDPOINT:
        raise PortablePackageEvalError(
            "package eval OpenAI transport is pinned to the official Responses endpoint"
        )
    return endpoint


def _sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _load_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise PortablePackageEvalError(f"cannot load JSON: {path}: {exc}") from exc
    if not isinstance(value, dict):
        raise PortablePackageEvalError(f"JSON root must be an object: {path}")
    return value


def _validate_capsule_artifact_digests(
    *, capsule_dir: Path, manifest: dict[str, Any]
) -> None:
    artifact_digests = manifest.get("artifact_digests")
    if not isinstance(artifact_digests, dict) or not artifact_digests:
        raise PortablePackageEvalError(
            "capsule manifest must bind non-empty artifact_digests"
        )

    for name, expected_sha in artifact_digests.items():
        if (
            not isinstance(name, str)
            or not name
            or Path(name).name != name
            or "/" in name
            or "\\" in name
        ):
            raise PortablePackageEvalError(
                "capsule artifact digest keys must be local filenames"
            )
        if (
            not isinstance(expected_sha, str)
            or len(expected_sha) != 64
            or any(ch not in "0123456789abcdef" for ch in expected_sha)
        ):
            raise PortablePackageEvalError(
                f"capsule artifact digest is invalid: {name}"
            )
        artifact_path = capsule_dir / name
        if not artifact_path.is_file():
            raise PortablePackageEvalError(
                f"capsule artifact missing: {name}"
            )
        actual_sha = _sha256_file(artifact_path)
        if actual_sha != expected_sha:
            raise PortablePackageEvalError(
                f"capsule artifact digest mismatch: {name}"
            )


def _validate_completed_response(
    *, label: str, response: dict[str, Any]
) -> str:
    if not isinstance(response, dict):
        raise PortablePackageEvalError(f"{label} response must be an object")
    response_id = response.get("id")
    if not isinstance(response_id, str) or not response_id.strip():
        raise PortablePackageEvalError(f"{label} response id must be non-empty")
    status = response.get("status")
    if status != "completed":
        raise PortablePackageEvalError(
            f"{label} response status must be completed"
        )
    return response_id.strip()


def build_responses_payload(
    *,
    request_contract: dict[str, Any],
    model: str,
    package_context: str | None,
) -> dict[str, Any]:
    if not isinstance(model, str) or not model.strip():
        raise PortablePackageEvalError("model must be a non-empty string")
    if request_contract.get("store") is not False:
        raise PortablePackageEvalError("package eval Responses requests must set store=false")
    treatment = request_contract.get("treatment")
    if treatment not in {"PACKAGE_OFF", "PACKAGE_ON"}:
        raise PortablePackageEvalError("unsupported package-eval treatment")

    tools = request_contract.get("allowed_tools", [])
    if not isinstance(tools, list):
        raise PortablePackageEvalError("allowed_tools must be a list")
    unsupported = sorted(set(tools) - SUPPORTED_TOOLS)
    if unsupported:
        raise PortablePackageEvalError(
            "unsupported Responses tools for package eval: " + ", ".join(unsupported)
        )

    input_items: list[dict[str, Any]] = []
    if treatment == "PACKAGE_ON":
        if not package_context:
            raise PortablePackageEvalError("PACKAGE_ON requires package context")
        instruction = request_contract.get("package_entry_instruction")
        if not isinstance(instruction, str) or not instruction.strip():
            raise PortablePackageEvalError("PACKAGE_ON requires package_entry_instruction")
        input_items.append({
            "role": "developer",
            "content": [{
                "type": "input_text",
                "text": instruction.strip() + "\n\n" + package_context,
            }],
        })
    elif package_context is not None:
        raise PortablePackageEvalError("PACKAGE_OFF may not receive package context")

    task_prompt = request_contract.get("task_prompt")
    if not isinstance(task_prompt, str) or not task_prompt.strip():
        raise PortablePackageEvalError("task_prompt must be a non-empty string")
    input_items.append({
        "role": "user",
        "content": [{"type": "input_text", "text": task_prompt.strip()}],
    })

    payload: dict[str, Any] = {
        "model": model.strip(),
        "store": False,
        "input": input_items,
    }
    if tools:
        payload["tools"] = [{"type": name} for name in tools]
    return payload


def _post_json(
    *,
    endpoint: str,
    api_key: str,
    payload: dict[str, Any],
    timeout_seconds: float,
) -> dict[str, Any]:
    if not api_key:
        raise PortablePackageEvalError("OpenAI API key is required")
    endpoint = _validate_openai_endpoint(endpoint)
    request = urllib.request.Request(
        endpoint,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    request.add_unredirected_header("Authorization", f"Bearer {api_key}")
    opener = urllib.request.build_opener(_NoRedirectHandler())
    try:
        with opener.open(request, timeout=timeout_seconds) as response:
            body = response.read()
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")[:2000]
        raise PortablePackageEvalError(
            f"Responses API HTTP {exc.code}: {detail}"
        ) from exc
    except urllib.error.URLError as exc:
        raise PortablePackageEvalError(f"Responses API transport failed: {exc}") from exc
    try:
        value = json.loads(body)
    except json.JSONDecodeError as exc:
        raise PortablePackageEvalError("Responses API returned invalid JSON") from exc
    if not isinstance(value, dict):
        raise PortablePackageEvalError("Responses API response must be an object")
    return value


def extract_output_text(response: dict[str, Any]) -> str:
    parts: list[str] = []
    for item in response.get("output", []):
        if not isinstance(item, dict) or item.get("type") != "message":
            continue
        for content in item.get("content", []):
            if isinstance(content, dict) and content.get("type") == "output_text":
                text = content.get("text")
                if isinstance(text, str):
                    parts.append(text)
    return "\n".join(parts).strip()


def execute_openai_pair(
    *,
    capsule_dir: Path,
    package_path: Path,
    model: str,
    api_key: str,
    output_dir: Path,
    endpoint: str = DEFAULT_RESPONSES_ENDPOINT,
    timeout_seconds: float = 300.0,
    transport: Callable[..., dict[str, Any]] | None = None,
) -> dict[str, Any]:
    capsule_dir = Path(capsule_dir)
    package_path = Path(package_path)
    output_dir = Path(output_dir)
    endpoint = _validate_openai_endpoint(endpoint)
    manifest = _load_json(capsule_dir / "eval-manifest.json")
    _validate_capsule_artifact_digests(
        capsule_dir=capsule_dir,
        manifest=manifest,
    )
    on_request = _load_json(capsule_dir / "package-on-request.json")
    off_request = _load_json(capsule_dir / "package-off-request.json")
    grader = _load_json(capsule_dir / "grader-contract.json")

    expected_package_sha = manifest.get("package", {}).get("sha256")
    if expected_package_sha != _sha256_file(package_path):
        raise PortablePackageEvalError(
            "package artifact does not match capsule manifest SHA-256"
        )

    output_dir.mkdir(parents=True, exist_ok=True)
    projection = compile_package_context(
        package_path=package_path,
        output_path=output_dir / "package-context.txt",
    )
    package_context = projection.output_path.read_text(encoding="utf-8")
    off_payload = build_responses_payload(
        request_contract=off_request,
        model=model,
        package_context=None,
    )
    on_payload = build_responses_payload(
        request_contract=on_request,
        model=model,
        package_context=package_context,
    )
    post = transport or _post_json

    off_response = post(
        endpoint=endpoint,
        api_key=api_key,
        payload=off_payload,
        timeout_seconds=timeout_seconds,
    )
    off_response_id = _validate_completed_response(
        label="PACKAGE_OFF",
        response=off_response,
    )
    on_response = post(
        endpoint=endpoint,
        api_key=api_key,
        payload=on_payload,
        timeout_seconds=timeout_seconds,
    )
    on_response_id = _validate_completed_response(
        label="PACKAGE_ON",
        response=on_response,
    )
    if off_response_id == on_response_id:
        raise PortablePackageEvalError(
            "paired Responses run must produce distinct response ids"
        )

    off_text = extract_output_text(off_response)
    on_text = extract_output_text(on_response)
    if not off_text or not on_text:
        raise PortablePackageEvalError(
            "paired Responses run must produce non-empty text for both treatments"
        )

    (output_dir / "package-off-response.json").write_text(
        json.dumps(off_response, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    (output_dir / "package-on-response.json").write_text(
        json.dumps(on_response, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    (output_dir / "package-off-output.txt").write_text(off_text, encoding="utf-8")
    (output_dir / "package-on-output.txt").write_text(on_text, encoding="utf-8")
    off_grade = grade_output_text(output_text=off_text, grader_contract=grader)
    on_grade = grade_output_text(output_text=on_text, grader_contract=grader)
    comparison = compare_grade_results(package_off=off_grade, package_on=on_grade)
    for name, value in (
        ("package-off-grade.json", off_grade),
        ("package-on-grade.json", on_grade),
        ("comparison.json", comparison),
    ):
        (output_dir / name).write_text(
            json.dumps(value, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )

    run_id = f"ppe-{uuid.uuid4()}"
    receipt = {
        "receipt_schema_version": "0.1",
        "run_id": run_id,
        "run_classification": "PORTABLE_PACKAGE_REGRESSION",
        "provider": "openai",
        "model": model,
        "endpoint": endpoint,
        "store": False,
        "package_sha256": expected_package_sha,
        "fixture_sha256": manifest.get("fixture_sha256"),
        "package_context_sha256": projection.sha256,
        "package_context_files": list(projection.included_files),
        "package_off_response_id": off_response_id,
        "package_on_response_id": on_response_id,
        "package_off_status": off_response.get("status"),
        "package_on_status": on_response.get("status"),
        "deterministic_comparison": comparison,
        "semantic_grade_status": "NOT_EXECUTED",
        "authority_transfer": False,
    }
    receipt_path = output_dir / "execution-receipt.json"
    receipt_path.write_text(
        json.dumps(receipt, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return receipt
