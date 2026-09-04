#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Tuple

ROOT = Path(__file__).resolve().parents[1]
EXACT_CANDIDATE_EXPR = "${{ github.event.pull_request.head.sha || github.sha }}"
CHECKOUT_PIN_RE = re.compile(r"^actions/checkout@[0-9a-f]{40}$")
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


def validate_workflow_text(path: str, text: str) -> List[Dict[str, str]]:
    errors: List[Dict[str, str]] = []
    if "pull_request:" not in text:
        return errors
    env_re = re.compile(
        r"^\s*AIOS_CANDIDATE_SHA:\s*\$\{\{ github\.event\.pull_request\.head\.sha \|\| github\.sha \}\}\s*$",
        re.MULTILINE,
    )
    if not env_re.search(text):
        errors.append({"code": "AOS-CI-CANDIDATE-ENV", "path": path, "message": "workflow must define AIOS_CANDIDATE_SHA from PR head SHA with github.sha fallback"})

    steps = _step_blocks(text)
    checkout_indexes: List[int] = []
    for idx, (indent, original, masked) in enumerate(steps):
        direct = _direct_map(indent, masked)
        uses = direct.get("uses", "")
        if uses.startswith("actions/checkout@"):
            checkout_indexes.append(idx)
            if not CHECKOUT_PIN_RE.fullmatch(uses):
                errors.append({"code": "AOS-CI-CHECKOUT-PIN", "path": path, "message": "actions/checkout must be pinned to a full commit SHA"})
            with_map = _with_map(indent, masked)
            if with_map.get("ref") != "${{ env.AIOS_CANDIDATE_SHA }}":
                errors.append({"code": "AOS-CI-CHECKOUT-REF", "path": path, "message": "checkout with.ref must directly equal ${{ env.AIOS_CANDIDATE_SHA }}"})
            if with_map.get("persist-credentials", "").lower() != "false":
                errors.append({"code": "AOS-CI-CHECKOUT-CREDENTIALS", "path": path, "message": "checkout must disable persisted credentials"})

    if not checkout_indexes:
        errors.append({"code": "AOS-CI-CHECKOUT-MISSING", "path": path, "message": "pull_request workflow must contain an exact-candidate checkout"})
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
        if "git rev-parse HEAD" not in body or "AIOS_CANDIDATE_SHA" not in body:
            errors.append({"code": "AOS-CI-IDENTITY-VERIFY", "path": path, "message": "identity verification must compare git HEAD with AIOS_CANDIDATE_SHA"})
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
        "schema": "AIOS_TOOLS_CI_EXACT_HEAD_AUDIT_01",
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
