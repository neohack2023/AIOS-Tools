# AT-GH-01 — Governed Repository Surface

## Frozen inputs

- `main`: `2e2c12100586dfa15036e2205e820c2d309238b5`
- bootstrap draft PR #1 head: `65ede6aa39f7db2428346d8c2a0d9eb44e5febca`
- prior verified CI run: `30236282600`

## Objective

Make AIOS-Tools understandable, safely editable, testable, and traceable without changing runtime behavior.

## Included

- repository map and authority boundaries
- agent and contributor instructions
- security baseline
- validation and development documentation
- pull-request evidence template
- deterministic repository-governance CI

## Non-goals

No runtime refactor, new tools, deployment, authentication, connector writes, branch-protection changes, auto-merge, package publication, or authority transfer.

## Validation

Run the existing shared-core tests, CLI smoke, and MCP smoke. Run the governance workflow and verify required files and authority language.

## Rollback

Close the draft PR and delete `agent/governed-repository-surface`. No changes are made to `main` or external systems.