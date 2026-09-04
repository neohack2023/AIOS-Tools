#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List

import yaml

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


class WorkflowLoader(yaml.BaseLoader):
    """Keep Actions scalar spellings; reject ambiguous duplicate mapping keys."""

    def construct_mapping(self, node, deep=False):
        result = {}
        for key_node, value_node in node.value:
            key = self.construct_object(key_node, deep=deep)
            if not isinstance(key, str) or key in result:
                raise ValueError("duplicate or non-scalar workflow key")
            result[key] = self.construct_object(value_node, deep=deep)
        return result


def _verification_enforces_compare(shell: str, body: str) -> bool:
    # This is a closed language, not a shell parser. Additional commands,
    # reordered assignments, folded scalars and custom shells fail closed.
    if not isinstance(body, str):
        return False
    bash = [
        "set -euo pipefail",
        f'expected="{EXACT_CANDIDATE_EXPR}"',
        'actual="$(git rev-parse HEAD)"',
        'test "$actual" = "$expected"',
    ]
    pwsh = [
        f"$expected = '{EXACT_CANDIDATE_EXPR}'",
        "$actual = git rev-parse HEAD",
        'if ($actual -ne $expected) { throw "Checkout mismatch: expected $expected, got $actual" }',
    ]
    lines = body.strip("\n").splitlines()
    if shell == "bash":
        return lines == bash or lines == bash + ['test "$expected" = "$AIOS_AUDIT_CANDIDATE_SHA"']
    return shell == "pwsh" and lines == pwsh


def validate_workflow_text(path: str, text: str) -> List[Dict[str, str]]:
    errors: List[Dict[str, str]] = []

    def fail(code, message):
        errors.append({"code": code, "path": path, "message": message})

    try:
        # Aliases/merge keys need an additional precedence contract; do not
        # silently certify them. BaseLoader also avoids YAML 1.1's on -> True.
        if any(isinstance(token, (yaml.tokens.AnchorToken, yaml.tokens.AliasToken))
               for token in yaml.scan(text)):
            raise ValueError("workflow anchors and aliases are unsupported")
        workflow = yaml.load(text, Loader=WorkflowLoader)
        if not isinstance(workflow, dict):
            raise ValueError("workflow must be a mapping")
    except (yaml.YAMLError, ValueError) as exc:
        fail("AOS-CI-WORKFLOW-SYNTAX", str(exc))
        return errors

    events = workflow.get("on")
    if (not isinstance(events, dict) or "pull_request" not in events
            or not re.search(r"^on:\s*$", text, re.MULTILINE)
            or not re.search(r"^  pull_request:\s*$", text, re.MULTILINE)):
        fail("AOS-CI-TRIGGER-SYNTAX", "canonical block-form on/pull_request is required")
    else:
        pr = events["pull_request"]
        if isinstance(pr, dict) and "paths" in pr:
            paths = pr["paths"]
            if not isinstance(paths, list) or path not in paths:
                fail("AOS-CI-SELF-TRIGGER", "path-filtered pull_request workflow must include its own workflow path")

    def inspect_controls(value):
        if isinstance(value, dict):
            if "AIOS_CANDIDATE_SHA" in value:
                fail("AOS-CI-CANDIDATE-SHADOW", "candidate environment indirection is forbidden")
            if "continue-on-error" in value and value["continue-on-error"] != "false":
                fail("AOS-CI-CONTINUE-ON-ERROR", "acceptance failure must be fatal")
            if "<<" in value:
                fail("AOS-CI-WORKFLOW-SYNTAX", "merge keys are unsupported")
            for child in value.values():
                inspect_controls(child)
        elif isinstance(value, list):
            for child in value:
                inspect_controls(child)

    inspect_controls(workflow)
    def check_identity_environment(scope):
        env = scope.get("env", {})
        if (not isinstance(env, dict)
                or set(env) - {"AIOS_AUDIT_CANDIDATE_SHA"}
                or (env and env.get("AIOS_AUDIT_CANDIDATE_SHA") != EXACT_CANDIDATE_EXPR)):
            fail("AOS-CI-IDENTITY-ENV", "inherited identity environment must use the audited candidate-only shape")

    check_identity_environment(workflow)
    jobs = workflow.get("jobs")
    if not isinstance(jobs, dict) or not jobs:
        fail("AOS-CI-CHECKOUT-MISSING", "audited workflow must contain jobs with exact-candidate checkouts")
        return errors
    for job in jobs.values():
        steps = job.get("steps") if isinstance(job, dict) else None
        if not isinstance(steps, list) or not all(isinstance(step, dict) for step in steps):
            fail("AOS-CI-WORKFLOW-SYNTAX", "audited jobs must declare a list of step mappings")
            continue
        check_identity_environment(job)
        checkouts = [i for i, step in enumerate(steps)
                     if isinstance(step.get("uses"), str) and step["uses"].startswith("actions/checkout@")]
        if not checkouts:
            fail("AOS-CI-CHECKOUT-MISSING", "each audited job must contain an exact-candidate checkout")
        if checkouts and checkouts[0] != 0:
            fail("AOS-CI-CHECKOUT-SHAPE", "the first job step must be the candidate checkout")
        for i in checkouts:
            checkout = steps[i]
            if not CHECKOUT_PIN_RE.fullmatch(checkout["uses"]):
                fail("AOS-CI-CHECKOUT-PIN", "actions/checkout must be pinned to a full commit SHA")
            inputs = checkout.get("with", {})
            if not isinstance(inputs, dict):
                inputs = {}
            if inputs.get("ref") != EXACT_CANDIDATE_EXPR:
                fail("AOS-CI-CHECKOUT-REF", "checkout ref must bind directly to GitHub candidate context")
            if inputs.get("persist-credentials") != "false":
                fail("AOS-CI-CHECKOUT-CREDENTIALS", "checkout must disable persisted credentials")
            if (set(checkout) - {"name", "uses", "with", "id", "continue-on-error"}
                    or set(inputs) - {"ref", "persist-credentials"}):
                fail("AOS-CI-CHECKOUT-SHAPE", "checkout controls and inputs must use the audited shape")
            if i + 1 >= len(steps):
                fail("AOS-CI-IDENTITY-VERIFY", "checkout must be followed immediately by identity verification in the same job")
                continue
            verify = steps[i + 1]
            if "if" in verify:
                fail("AOS-CI-IDENTITY-CONDITION", "identity verification may not be conditional")
            allowed = {"name", "shell", "run", "working-directory", "continue-on-error"}
            name = verify.get("name", "")
            if (set(verify) - allowed or not isinstance(name, str)
                    or "Verify" not in name or "checkout identity" not in name.lower()
                    or not _verification_enforces_compare(verify.get("shell"), verify.get("run"))):
                fail("AOS-CI-IDENTITY-VERIFY", "identity verification must match a complete audited step and ordered command body")
            # Resolve inherited run-directory defaults; a neighboring checkout
            # or a narrower step directory must not provide the comparison.
            directory = "${{ github.workspace }}"
            for scope in (workflow, job):
                defaults = scope.get("defaults", {})
                if isinstance(defaults, dict) and isinstance(defaults.get("run", {}), dict):
                    directory = defaults.get("run", {}).get("working-directory", directory)
                else:
                    directory = None
            directory = verify.get("working-directory", directory)
            if directory != "${{ github.workspace }}":
                fail("AOS-CI-IDENTITY-DIRECTORY", "identity must be verified in github.workspace")
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
