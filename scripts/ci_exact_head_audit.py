#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

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
DANGEROUS_IDENTITY_ENV = {
    "BASH_ENV",
    "ENV",
    "PATH",
    "GIT_DIR",
    "GIT_WORK_TREE",
    "GIT_INDEX_FILE",
    "GIT_OBJECT_DIRECTORY",
    "GIT_ALTERNATE_OBJECT_DIRECTORIES",
    "SHELLOPTS",
    "BASHOPTS",
}


class WorkflowLoader(yaml.BaseLoader):
    """Preserve Actions scalar spellings and reject duplicate mapping keys."""

    def construct_mapping(self, node, deep=False):
        result = {}
        for key_node, value_node in node.value:
            key = self.construct_object(key_node, deep=deep)
            if not isinstance(key, str) or key in result:
                raise ValueError("duplicate or non-scalar workflow key")
            result[key] = self.construct_object(value_node, deep=deep)
        return result


def _load_workflow(text: str) -> dict[str, Any]:
    if any(
        isinstance(token, (yaml.tokens.AnchorToken, yaml.tokens.AliasToken))
        for token in yaml.scan(text)
    ):
        raise ValueError("workflow anchors and aliases are unsupported by the AIOS policy layer")
    workflow = yaml.load(text, Loader=WorkflowLoader)
    if not isinstance(workflow, dict):
        raise ValueError("workflow must be a mapping")
    return workflow


def _fatal(value: Any) -> bool:
    return value in (None, "", "false", False)


def _verify_body(shell: str, body: Any) -> bool:
    if not isinstance(body, str):
        return False
    lines = body.strip("\n").splitlines()
    if shell == "bash":
        return lines in (
            [
                "set -euo pipefail",
                f'expected="{EXACT_CANDIDATE_EXPR}"',
                'actual="$(git rev-parse HEAD)"',
                'test "$actual" = "$expected"',
            ],
            [
                "set -euo pipefail",
                f'expected="{EXACT_CANDIDATE_EXPR}"',
                'actual="$(git rev-parse HEAD)"',
                'test "$actual" = "$expected"',
                'test "$expected" = "$AIOS_AUDIT_CANDIDATE_SHA"',
            ],
        )
    if shell == "pwsh":
        return lines == [
            f"$expected = '{EXACT_CANDIDATE_EXPR}'",
            "$actual = git rev-parse HEAD",
            'if ($actual -ne $expected) { throw "Checkout mismatch: expected $expected, got $actual" }',
        ]
    return False


def _dangerous_env(scope: Any) -> set[str]:
    if not isinstance(scope, dict):
        return set()
    env = scope.get("env")
    if not isinstance(env, dict):
        return set()
    return DANGEROUS_IDENTITY_ENV.intersection(env)


def _validate_trigger(path: str, workflow: dict[str, Any], fail) -> None:
    events = workflow.get("on")
    if not isinstance(events, dict) or "pull_request" not in events:
        fail("AOS-CI-PR-TRIGGER", "audited workflow must define a pull_request trigger")
        return

    pr = events["pull_request"]
    if pr in ("", None):
        return
    if not isinstance(pr, dict):
        fail("AOS-CI-PR-TRIGGER", "pull_request configuration must be a mapping or empty")
        return

    if "paths-ignore" in pr:
        fail(
            "AOS-CI-SELF-TRIGGER",
            "audited workflows may not use pull_request.paths-ignore; workflow edits must always be observable",
        )

    paths = pr.get("paths")
    if paths is None:
        return
    if not isinstance(paths, list) or not all(isinstance(item, str) for item in paths):
        fail("AOS-CI-SELF-TRIGGER", "pull_request.paths must be a list of strings")
        return
    if any(item.startswith("!") for item in paths):
        fail(
            "AOS-CI-SELF-TRIGGER",
            "negative pull_request.paths patterns are forbidden for audited workflows",
        )
    if path not in paths:
        fail(
            "AOS-CI-SELF-TRIGGER",
            "path-filtered workflow must include its own workflow path exactly",
        )


def validate_workflow_text(path: str, text: str) -> list[dict[str, str]]:
    """Check only AIOS trust-binding policy.

    Generic GitHub Actions syntax/semantics are delegated to actionlint.
    Generic workflow security analysis is delegated to zizmor.
    """
    errors: list[dict[str, str]] = []

    def fail(code: str, message: str) -> None:
        errors.append({"code": code, "path": path, "message": message})

    try:
        workflow = _load_workflow(text)
    except (yaml.YAMLError, ValueError) as exc:
        fail("AOS-CI-POLICY-PARSE", str(exc))
        return errors

    _validate_trigger(path, workflow, fail)

    dangerous = _dangerous_env(workflow)
    if dangerous:
        fail(
            "AOS-CI-IDENTITY-ENV",
            f"workflow environment may not override identity-sensitive variables: {sorted(dangerous)}",
        )

    jobs = workflow.get("jobs")
    if not isinstance(jobs, dict) or not jobs:
        fail("AOS-CI-JOBS", "audited workflow must define jobs")
        return errors

    for job_name, job in jobs.items():
        if not isinstance(job, dict):
            fail("AOS-CI-JOB-SHAPE", f"job {job_name!r} must be a mapping")
            continue
        if "container" in job:
            fail(
                "AOS-CI-EXECUTION-CONTEXT",
                f"job {job_name!r} may not use a container; exact-head verification must run in the declared runner environment",
            )
        if not _fatal(job.get("continue-on-error")):
            fail("AOS-CI-CONTINUE-ON-ERROR", f"job {job_name!r} must fail closed")
        dangerous = _dangerous_env(job)
        if dangerous:
            fail(
                "AOS-CI-IDENTITY-ENV",
                f"job {job_name!r} may not override identity-sensitive variables: {sorted(dangerous)}",
            )

        steps = job.get("steps")
        if not isinstance(steps, list) or len(steps) < 2 or not all(isinstance(step, dict) for step in steps):
            fail("AOS-CI-JOB-SHAPE", f"job {job_name!r} must begin with checkout and identity-verification steps")
            continue

        checkout, verify = steps[0], steps[1]
        uses = checkout.get("uses")
        if not isinstance(uses, str) or not CHECKOUT_PIN_RE.fullmatch(uses):
            fail("AOS-CI-CHECKOUT-PIN", f"job {job_name!r} first step must be full-SHA-pinned actions/checkout")
        if "if" in checkout or not _fatal(checkout.get("continue-on-error")):
            fail("AOS-CI-CHECKOUT-SHAPE", f"job {job_name!r} checkout may not be conditional or non-fatal")
        inputs = checkout.get("with")
        if not isinstance(inputs, dict):
            inputs = {}
        if set(inputs) != {"ref", "persist-credentials"}:
            fail("AOS-CI-CHECKOUT-SHAPE", f"job {job_name!r} checkout inputs must be exactly ref and persist-credentials")
        if inputs.get("ref") != EXACT_CANDIDATE_EXPR:
            fail("AOS-CI-CHECKOUT-REF", f"job {job_name!r} checkout must bind directly to immutable candidate context")
        if inputs.get("persist-credentials") != "false":
            fail("AOS-CI-CHECKOUT-CREDENTIALS", f"job {job_name!r} checkout must disable persisted credentials")

        if "if" in verify or not _fatal(verify.get("continue-on-error")):
            fail("AOS-CI-IDENTITY-CONDITION", f"job {job_name!r} identity verification must be unconditional and fatal")
        name = verify.get("name")
        shell = verify.get("shell")
        if not isinstance(name, str) or "checkout identity" not in name.lower():
            fail("AOS-CI-IDENTITY-VERIFY", f"job {job_name!r} second step must be named checkout identity verification")
        if not _verify_body(shell, verify.get("run")):
            fail("AOS-CI-IDENTITY-VERIFY", f"job {job_name!r} identity verifier must match the closed Bash/PowerShell contract")

        defaults = job.get("defaults")
        inherited_dir = None
        workflow_defaults = workflow.get("defaults")
        for scope_defaults in (workflow_defaults, defaults):
            if isinstance(scope_defaults, dict):
                run_defaults = scope_defaults.get("run")
                if isinstance(run_defaults, dict) and "working-directory" in run_defaults:
                    inherited_dir = run_defaults["working-directory"]
        verify_dir = verify.get("working-directory", inherited_dir)
        if verify_dir not in (None, "${{ github.workspace }}"):
            fail("AOS-CI-IDENTITY-DIRECTORY", f"job {job_name!r} must verify identity in github.workspace")

    return errors


def validate_repository_workflows(root: Path = ROOT) -> list[dict[str, str]]:
    errors: list[dict[str, str]] = []
    for rel in WORKFLOW_PATHS:
        workflow = root / rel
        if not workflow.is_file():
            errors.append({"code": "AOS-CI-WORKFLOW-MISSING", "path": rel, "message": "required acceptance workflow is missing"})
            continue
        errors.extend(validate_workflow_text(rel, workflow.read_text(encoding="utf-8")))
    return errors


def audit(root: Path = ROOT) -> dict[str, object]:
    errors = validate_repository_workflows(root)
    return {
        "schema": "AIOS_TOOLS_CI_EXACT_HEAD_POLICY_04",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "result": "PASS" if not errors else "FAIL",
        "generic_syntax_verifier": "actionlint@1.7.12",
        "generic_security_evidence": "zizmor@1.29.0",
        "policy_scope": "AIOS exact-head identity, self-trigger observability, and verifier execution context",
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
