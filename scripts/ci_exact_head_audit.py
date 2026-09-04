#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Tuple

ROOT = Path(__file__).resolve().parents[1]
CHECKOUT_PIN_RE = re.compile(r"^actions/checkout@[0-9a-f]{40}$")
EXACT_CANDIDATE_EXPR = "${{ github.event.pull_request.head.sha || github.sha }}"
WORKFLOW_PATHS = (
    ".github/workflows/audio-model-dependency-lock.yml",
    ".github/workflows/benchmark-registry.yml",
    ".github/workflows/browser-activation-replay.yml",
    ".github/workflows/ci.yml",
    ".github/workflows/demucs-model-quarantine.yml",
    ".github/workflows/repo-governance.yml",
)


def _indent(line: str) -> int:
    return len(line) - len(line.lstrip(" "))


def _mask_block_scalars(lines: List[str]) -> List[str]:
    masked = list(lines)
    scalar_indent = None
    for idx, line in enumerate(lines):
        if scalar_indent is not None:
            if line.strip() and _indent(line) <= scalar_indent:
                scalar_indent = None
            else:
                masked[idx] = ""
                continue
        if re.match(r"^\s+(run|script):\s*[|>]", line):
            scalar_indent = _indent(line)
    return masked


def _step_blocks(text: str) -> List[Tuple[int, List[str], List[str]]]:
    original = text.splitlines()
    masked = _mask_block_scalars(original)
    starts: List[Tuple[int, int]] = []
    for idx, line in enumerate(masked):
        match = re.match(r"^(\s*)-\s+(name|uses):", line)
        if match:
            starts.append((idx, len(match.group(1))))
    blocks: List[Tuple[int, List[str], List[str]]] = []
    for pos, (start, indent) in enumerate(starts):
        end = len(original)
        for next_start, next_indent in starts[pos + 1 :]:
            if next_indent == indent:
                end = next_start
                break
        blocks.append((indent, original[start:end], masked[start:end]))
    return blocks


def _direct_map(step_indent: int, lines: List[str]) -> Dict[str, str]:
    out: Dict[str, str] = {}
    target_indent = step_indent + 2
    for line in lines:
        if not line.strip() or _indent(line) != target_indent:
            continue
        stripped = line.strip()
        if ":" not in stripped:
            continue
        key, value = stripped.split(":", 1)
        out[key.strip()] = value.strip().strip('"').strip("'")
    first = lines[0].strip() if lines else ""
    if first.startswith("- ") and ":" in first:
        key, value = first[2:].split(":", 1)
        out[key.strip()] = value.strip().strip('"').strip("'")
    return out


def _with_map(step_indent: int, lines: List[str]) -> Dict[str, str]:
    with_indent = step_indent + 2
    child_indent = step_indent + 4
    in_with = False
    out: Dict[str, str] = {}
    for line in lines:
        if not line.strip():
            continue
        current = _indent(line)
        stripped = line.strip()
        if current == with_indent and stripped == "with:":
            in_with = True
            continue
        if in_with and current <= with_indent:
            in_with = False
        if in_with and current == child_indent and ":" in stripped:
            key, value = stripped.split(":", 1)
            out[key.strip()] = value.strip().strip('"').strip("'")
    return out


def _run_body(step_indent: int, original_lines: List[str]) -> str:
    run_indent = step_indent + 2
    capture = False
    body: List[str] = []
    for line in original_lines:
        if not line.strip():
            if capture:
                body.append("")
            continue
        current = _indent(line)
        stripped = line.strip()
        if current == run_indent and re.match(r"^run:\s*[|>]", stripped):
            capture = True
            continue
        if capture and current <= run_indent:
            break
        if capture:
            body.append(stripped)
    return "\n".join(body)


def _canonical_pull_request_trigger(text: str) -> bool:
    """Accept only the repository's canonical block-form on/pull_request shape.

    Alternative valid YAML spellings fail closed instead of being mistaken for
    a non-PR workflow, preventing syntax-only rewrites from bypassing the audit.
    """
    lines = _mask_block_scalars(text.splitlines())
    on_index = None
    for idx, line in enumerate(lines):
        if re.fullmatch(r"on:\s*", line):
            on_index = idx
            break
    if on_index is None:
        return False
    for line in lines[on_index + 1 :]:
        if not line.strip():
            continue
        current = _indent(line)
        if current == 0:
            break
        if current == 2 and re.fullmatch(r"pull_request:\s*", line.strip()):
            return True
    return False


def _pull_request_paths(text: str) -> List[str] | None:
    lines = _mask_block_scalars(text.splitlines())
    start = None
    pr_indent = None
    for idx, line in enumerate(lines):
        match = re.match(r"^(\s*)pull_request:\s*$", line)
        if match:
            start = idx
            pr_indent = len(match.group(1))
            break
    if start is None or pr_indent is None:
        return None
    paths_indent = None
    for idx in range(start + 1, len(lines)):
        line = lines[idx]
        if not line.strip():
            continue
        current = _indent(line)
        if current <= pr_indent:
            break
        if current == pr_indent + 2 and line.strip() == "paths:":
            paths_indent = current
            start = idx
            break
    if paths_indent is None:
        return None
    paths: List[str] = []
    for line in lines[start + 1 :]:
        if not line.strip():
            continue
        current = _indent(line)
        if current <= paths_indent:
            break
        if current == paths_indent + 2 and line.strip().startswith("- "):
            paths.append(line.strip()[2:].strip().strip('"').strip("'"))
    return paths


def _has_nonfatal_continue_on_error(text: str) -> bool:
    """Fail closed on any effective continue-on-error in audited workflows.

    Acceptance workflows may use literal `continue-on-error: false`, but true,
    expressions, or any other value are rejected at either step or job scope.
    """
    for line in _mask_block_scalars(text.splitlines()):
        if not line.strip():
            continue
        match = re.match(r"^\s*continue-on-error:\s*(.*?)\s*$", line)
        if match and match.group(1).strip().strip('"').strip("'").lower() != "false":
            return True
    return False


def _verification_enforces_compare(shell: str, body: str) -> bool:
    lines = [line.strip() for line in body.splitlines() if line.strip()]
    shell = shell.lower()
    if shell in {"pwsh", "powershell"}:
        expected_line = f"$expected = '{EXACT_CANDIDATE_EXPR}'"
        has_expected = expected_line in lines
        has_actual = any(re.fullmatch(r"\$actual\s*=\s*git\s+rev-parse\s+HEAD", line, re.IGNORECASE) for line in lines)
        has_reject = any(
            re.fullmatch(r'if\s*\(\s*\$actual\s+-ne\s+\$expected\s*\)\s*\{\s*throw\s+"[^"]+"\s*\}', line, re.IGNORECASE)
            for line in lines
        )
        return has_expected and has_actual and has_reject

    expected_line = f'expected="{EXACT_CANDIDATE_EXPR}"'
    has_expected = expected_line in lines
    has_actual = 'actual="$(git rev-parse HEAD)"' in lines
    has_exact_test = 'test "$actual" = "$expected"' in lines
    return has_expected and has_actual and has_exact_test


def validate_workflow_text(path: str, text: str) -> List[Dict[str, str]]:
    errors: List[Dict[str, str]] = []
    if not _canonical_pull_request_trigger(text):
        errors.append({
            "code": "AOS-CI-TRIGGER-SYNTAX",
            "path": path,
            "message": "audited workflow must use canonical block-form on: with direct pull_request: child; unsupported trigger syntax fails closed",
        })

    if re.search(r"^\s*AIOS_CANDIDATE_SHA\s*:", text, re.MULTILINE):
        errors.append({
            "code": "AOS-CI-CANDIDATE-SHADOW",
            "path": path,
            "message": "AIOS_CANDIDATE_SHA environment indirection is forbidden; checkout must bind directly to immutable GitHub event context",
        })

    if _has_nonfatal_continue_on_error(text):
        errors.append({
            "code": "AOS-CI-CONTINUE-ON-ERROR",
            "path": path,
            "message": "acceptance-relevant workflows may not suppress step or job failure with continue-on-error",
        })

    pr_paths = _pull_request_paths(text)
    if pr_paths is not None and path not in pr_paths:
        errors.append({"code": "AOS-CI-SELF-TRIGGER", "path": path, "message": "path-filtered pull_request workflow must include its own workflow path"})

    steps = _step_blocks(text)
    checkout_indexes: List[int] = []
    for idx, (indent, _original, masked) in enumerate(steps):
        direct = _direct_map(indent, masked)
        uses = direct.get("uses", "")
        if uses.startswith("actions/checkout@"):
            checkout_indexes.append(idx)
            if not CHECKOUT_PIN_RE.fullmatch(uses):
                errors.append({"code": "AOS-CI-CHECKOUT-PIN", "path": path, "message": "actions/checkout must be pinned to a full commit SHA"})
            with_map = _with_map(indent, masked)
            if with_map.get("ref") != EXACT_CANDIDATE_EXPR:
                errors.append({"code": "AOS-CI-CHECKOUT-REF", "path": path, "message": f"checkout with.ref must directly equal {EXACT_CANDIDATE_EXPR}"})
            if with_map.get("persist-credentials", "").lower() != "false":
                errors.append({"code": "AOS-CI-CHECKOUT-CREDENTIALS", "path": path, "message": "checkout must disable persisted credentials"})

    if not checkout_indexes:
        errors.append({"code": "AOS-CI-CHECKOUT-MISSING", "path": path, "message": "audited workflow must contain an exact-candidate checkout"})
        return errors

    for idx in checkout_indexes:
        if idx + 1 >= len(steps):
            errors.append({"code": "AOS-CI-IDENTITY-VERIFY", "path": path, "message": "checkout must be followed immediately by an identity verification step"})
            continue
        indent, original, masked = steps[idx + 1]
        direct = _direct_map(indent, masked)
        body = _run_body(indent, original)
        if "Verify" not in direct.get("name", "") or "checkout identity" not in direct.get("name", "").lower():
            errors.append({"code": "AOS-CI-IDENTITY-VERIFY", "path": path, "message": "checkout must be followed immediately by a named checkout identity verification step"})
            continue
        if direct.get("continue-on-error", "false").lower() != "false":
            errors.append({"code": "AOS-CI-CONTINUE-ON-ERROR", "path": path, "message": "checkout identity verification must be fatal on mismatch"})
            continue
        if not _verification_enforces_compare(direct.get("shell", "bash"), body):
            errors.append({"code": "AOS-CI-IDENTITY-VERIFY", "path": path, "message": "identity verification must use the constrained exact comparison against immutable GitHub candidate context"})
    return errors


def validate_repository_workflows(root: Path = ROOT) -> List[Dict[str, str]]:
    errors: List[Dict[str, str]] = []
    for rel in WORKFLOW_PATHS:
        path = root / rel
        if not path.is_file():
            errors.append({"code": "AOS-CI-WORKFLOW-MISSING", "path": rel, "message": "required acceptance-relevant workflow is missing"})
            continue
        errors.extend(validate_workflow_text(rel, path.read_text(encoding="utf-8")))
    return errors


def audit(root: Path = ROOT) -> Dict[str, object]:
    errors = validate_repository_workflows(root)
    return {
        "schema": "AIOS_TOOLS_CI_EXACT_HEAD_AUDIT_03",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "result": "PASS" if not errors else "FAIL",
        "workflows": list(WORKFLOW_PATHS),
        "errors": errors,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", default="outputs/ci-exact-head-audit.json")
    args = parser.parse_args()
    report = audit()
    out = ROOT / args.output
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0 if report["result"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
