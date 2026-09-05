# PR 59 verification-step repair

Input: `2eb51fda5e794037f8c0d0c48f17983251834ea5` on
`aios/exact-head-ci-binding-01`; base `758680ac0eb33e0ac82a3d099c7282b086bf0c04`.
Owner request: finish the repeated review repair cycle, review `5118604653`.
Governing repository contract: `docs/agent-system/audit/AUDIT_CONTRACT.md`,
implementing promoted `LESSON-AIOS-TOOLS-001`.

Scope: replace fragment-based workflow inspection with YAML structure and a
closed verification-step language; cover conditional execution, complete shell
bodies, same-job adjacency and related syntax/control bypasses. Update parser
development dependency and governance setup together. No runtime capability,
merge, release, global canon, freshness or branch-protection changes.

Files: auditor, focused regressions, pyproject, governance workflow, existing
audit contract and this plan/evidence record.

Validation: exact-head audit; organization and governance-sync audits; focused
regressions including actual Bash success/mismatch execution; required pytest
and CLI/MCP smoke checks; fresh remote CI on the final pushed commit.

Risk: intentionally narrower accepted workflow syntax; future verifier changes
must update the audited body and tests deliberately. PyYAML is pinned as a dev
and governance dependency. PowerShell execution is verified by Windows CI.
Rollback: revert this bounded repair commit on the PR branch; do not rewrite
history or reuse stale review/merge authorization.

Local repair verification (2026-09-04; working tree derived from input above):
- `python -m pip install -e '.[dev]'`: PASS.
- `python -m pytest -vv`: 360 passed, 8 skipped, exit 0.
- Focused exact-head unittest suite: 21 tests PASS, including parameterized
  adversarial cases and real Bash comparison success/mismatch execution.
- Organization auditor unittest suite: 4 PASS; governance sync suite: 4 PASS.
- Exact-head, Phase 5 organization and governance-sync audits: PASS.
- CLI list, read-only system.health and MCP --help: PASS.
- `git diff --check`: PASS.

The checkout must be the first job step, and workflow/job inherited environment
is limited to the existing directly bound audit candidate variable. This closes
pre-verification startup-environment and alternate Git-directory controls.
Remote exact-head CI and independent review remain the post-push gates. Local
working-tree results are not represented as evidence for the unchanged input SHA.
