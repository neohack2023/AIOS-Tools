# AIOS-Tools Repository Handoff

State: `PHASE_5_ACTIVE / PHASE_5_COMPLETE / SELF_SUFFICIENT_REPO_ACTIVE / LOCAL_CONTEXT_LIVE / NATIVE_AGENT_ADAPTERS_ACTIVE / NATIVE_SKILLS_ACTIVE / LEARNING_LOOP_ACTIVE / ORGANIZATION_AUDIT_ACTIVE / GOVERNANCE_SYNC_ACTIVE / EXACT_HEAD_POLICY_ACTIVE`

## Repository identity

- Repository: `neohack2023/AIOS-Tools`
- Default branch: `main`
- Frozen Phase 0 input head: `a8b47f74f0d2f7e6bcfaf25399ebc5ce7dd48e20`
- Phase 0 profile commit: `1550dcb6a5b39ed79f41bb6d124736b2b72c2871`
- Phase 1 staged head: `335c4e31c53ef3a2f8e4612fa60a7d13178e61ec`
- Phase 2 staged head: `6c5228d49c297b8268eb761e1e0f250245b57c52`
- Phase 3 staged head: `0c339033368b4d26c448041ad03900142d05ba73`
- Phase 4 validated head: `535c64226a4f4938941707b4e700273e85260846`
- Phase 5 installed head: `758680ac0eb33e0ac82a3d099c7282b086bf0c04`
- Exact-head verifier architecture main anchor: `4907b031e6d82b6989b044fddbc6408d16ada2c1`
- Blocking Actions-security baseline main anchor: `ae427d56f8fb4da3d6ea89033755cdf9f1d10858`

Resolve current mutable branch/head/PR/CI facts live from GitHub. Historical SHAs above are provenance anchors, not timeless claims about current `main`.

## Mission

AIOS-Tools is the governed capability and execution layer for AIOS. It provides the shared Python core plus CLI, MCP, browser, benchmark, cartography/web, and connector/tool surfaces while preserving fail-closed policy and evidence boundaries.

## Current operating model

Phase 1 made ordinary bootstrap local-first. Phase 2 added native roles and path departments. Phase 3 added reusable procedures and a candidate learning loop. Phase 4 added deterministic self-audit. Phase 5 adds bounded upstream resupply while keeping ordinary repository work external-fetch-free.

For GitHub Actions verification the responsibility split is now:

`actionlint -> generic Actions syntax/semantics`

`zizmor -> generic workflow-security evidence`

`AIOS policy verifier -> exact-head identity + self-trigger observability + verifier execution context + evidence binding`

AIOS does not reconstruct the entire GitHub Actions language with source-text heuristics.

## Phase 5 surfaces

- `.github/skills/sync-governance/SKILL.md` — Knowledge Steward procedure.
- `docs/agent-system/governance-sync/UPSTREAM_SYNC_PROFILE.md` — target-specific stable source set.
- `docs/agent-system/governance-sync/receipts/GSYNC-AIOS-TOOLS-20260904-001.json` — immutable historical pending comparison.
- `docs/agent-system/governance-sync/receipts/GSYNC-AIOS-TOOLS-20260904-002.json` — post-repair reconciliation and freshness-renewal receipt.
- `scripts/governance_sync.py` + `tests/test_governance_sync.py` — deterministic receipt/freshness validator.
- `scripts/agent_system_audit_phase5.py` — Phase 5 composition over the Phase 4 auditor.
- `.github/workflows/repo-governance.yml` — mechanical owner for actionlint, blocking zizmor, organization audit, exact-head policy, and sync validation.

## Agent/skill binding

- Coordinator -> `plan-feature`
- Reviewer -> `review-pr`
- Verifier -> `verify-head`
- Knowledge Steward -> `harvest-lesson`
- Knowledge Steward -> `sync-governance`
- Implementer -> no distinct skill yet; follows repository law + touched-area packet + governing plan.

Role identity and skill invocation do not grant merge, release, deploy, capability, verifier-class, mutation, or global-governance authority.

## Upstream governance source set

Routine governance synchronization is limited to:
1. `AIOS_TOOLS_EXECUTION_LAYER_CONTRACT` — repository architectural role and authority split.
2. `AIOS_GITHUB_GOVERNED_EXECUTION_CONTRACT_v0.1` — repository delivery/governance law.
3. `VERIFIER_OWNED_ACCEPTANCE_01` — verifier/acceptance law.

Related plans, receipts, research, and runtime feature contracts are evidence/history, not recurring authority merely because they are nearby.

## Phase 5 synchronization history

Receipt `GSYNC-AIOS-TOOLS-20260904-001` remains historically `MATERIAL_DELTA_PENDING`. It recorded the unresolved exact-head acceptance delta and did not renew freshness.

That delta was then explicitly adjudicated and repaired. `LESSON-AIOS-TOOLS-001` is `PROMOTED`; acceptance-relevant workflows bind to the exact candidate identity; actionlint owns generic Actions semantics; zizmor is blocking for generic workflow security; the focused AIOS policy verifier owns only AIOS-specific trust-binding obligations. PR #59 was closed unmerged and preserved as provenance after the owner-authorized architectural repair superseded it on `main`.

Receipt `GSYNC-AIOS-TOOLS-20260904-002` rechecks the same three upstream authorities, classifies both material deltas `RECONCILED`, records `MATERIAL_DELTA_RECONCILED`, and applies the permitted 30-day freshness renewal. Because the resync occurs on the same local date as the first receipt, `valid_through` remains `2026-10-04` while the renewal state changes from withheld to applied.

## Governance freshness

`docs/agent-system/context/governance-lock.yaml` is bundle version `0.6`, `sync_state: ACTIVE`, and valid through `2026-10-04`.

`NORMAL_REPO_WORK_EXTERNAL_FETCH_REQUIRED = FALSE`.

A future synchronization is triggered only by stale/expiring governance, suspected cross-repository governance drift, unresolved authority conflict/material incompleteness, or explicit owner direction. Successful fetch alone never renews freshness.

## Learning loop

`review/incident/verification finding -> harvest-lesson -> candidate memory -> human/governance adjudication -> smallest promoted rule/test/contract surface OR rejection`

`LESSON-AIOS-TOOLS-001` is promoted. Its acceptance effect remains obligation-scoped and grants no merge/release/deploy/capability authority.

## Independent risks carried forward

- branch protection remains a separate governance choice and is not changed by Phase 5;
- capability/network/write authority remains governed independently;
- a single browser storage-state fixture failure on CI attempt 1 passed on an unchanged exact-head rerun and is retained as nondeterministic evidence, not silently converted into an application repair.

## Terminal gate

`AIOS_TOOLS_PHASE_5 / SELF_SUFFICIENT_REPO_ACTIVE / UPSTREAM_SYNC_ACTIVE / MATERIAL_DELTA_RECONCILED / FRESHNESS_RENEWED / NORMAL_REPO_WORK_EXTERNAL_FETCH_REQUIRED_FALSE / GOVERNANCE_VALID_THROUGH_2026-10-04`
