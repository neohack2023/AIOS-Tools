# AIOS-Tools Repository Handoff

State: `PHASE_5_ACTIVE / LOCAL_CONTEXT_LIVE / NATIVE_AGENT_ADAPTERS_ACTIVE / NATIVE_SKILLS_ACTIVE / LEARNING_LOOP_ACTIVE / ORGANIZATION_AUDIT_ACTIVE / GOVERNANCE_SYNC_ACTIVE / MATERIAL_DELTA_PENDING`

## Repository identity

- Repository: `neohack2023/AIOS-Tools`
- Default branch: `main`
- Frozen Phase 0 input head: `a8b47f74f0d2f7e6bcfaf25399ebc5ce7dd48e20`
- Phase 0 profile commit: `1550dcb6a5b39ed79f41bb6d124736b2b72c2871`
- Phase 1 staged head: `335c4e31c53ef3a2f8e4612fa60a7d13178e61ec`
- Phase 2 staged head: `6c5228d49c297b8268eb761e1e0f250245b57c52`
- Phase 3 staged head: `0c339033368b4d26c448041ad03900142d05ba73`
- Phase 4 validated head: `535c64226a4f4938941707b4e700273e85260846`

Resolve current mutable branch/head/PR/CI facts live from GitHub. Historical SHAs above are provenance anchors, not timeless claims about current `main`.

## Mission

AIOS-Tools is the governed capability and execution layer for AIOS. It provides the shared Python core plus CLI, MCP, browser, benchmark, cartography/web, and connector/tool surfaces while preserving fail-closed policy and evidence boundaries.

## Current operating model

Phase 1 made ordinary bootstrap local-first. Phase 2 added native roles and path departments. Phase 3 added reusable procedures and a candidate learning loop. Phase 4 added deterministic self-audit. Phase 5 adds a bounded resupply path without restoring ambient Notion/Drive dependence.

Phase 5 surfaces:
- `.github/skills/sync-governance/SKILL.md` — Knowledge Steward procedure;
- `docs/agent-system/governance-sync/UPSTREAM_SYNC_PROFILE.md` — target-specific pinned source set;
- `docs/agent-system/governance-sync/receipts/GSYNC-AIOS-TOOLS-20260904-001.json` — first immutable comparison receipt;
- `scripts/governance_sync.py` + `tests/test_governance_sync.py` — deterministic receipt/freshness validator;
- `scripts/agent_system_audit_phase5.py` — Phase 5 composition over the proven Phase 4 auditor;
- `.github/workflows/repo-governance.yml` — mechanical owner for organization and sync validation.

## Phase 2 departments

1. browser capability;
2. benchmark registry;
3. audio/model dependency and quarantine;
4. cartography/web;
5. shared execution core and adapters.

These are context-routing boundaries, not ownership or authorization stores.

## Agent/skill binding

- Coordinator -> `plan-feature`
- Reviewer -> `review-pr`
- Verifier -> `verify-head`
- Knowledge Steward -> `harvest-lesson`
- Knowledge Steward -> `sync-governance`
- Implementer -> no distinct skill yet; follows repository law + touched-area packet + governing plan

Role identity and skill invocation do not grant merge, release, deploy, capability, verifier-class, mutation, or global-governance authority.

## Upstream governance source set

Routine governance synchronization is limited to:
1. `AIOS_TOOLS_EXECUTION_LAYER_CONTRACT` — repository architectural role and authority split;
2. `AIOS_GITHUB_GOVERNED_EXECUTION_CONTRACT_v0.1` — repository delivery/governance law;
3. `VERIFIER_OWNED_ACCEPTANCE_01` — verifier/acceptance law.

Related plans, receipts, research, and runtime feature contracts are evidence/history, not recurring authority merely because they are nearby.

## First Phase 5 synchronization

Receipt: `GSYNC-AIOS-TOOLS-20260904-001`.

Overall disposition: `MATERIAL_DELTA_PENDING`.

- Reconciled: the upstream branch/PR default versus the explicit owner-authorized direct-main staging episodes. Local repository law still makes branch/PR delivery the default; staging exceptions are bounded and non-reusable.
- Pending: verifier-owned acceptance requires exact artifact/head identity for acceptance-owning evidence, while broader AIOS-Tools CI checkout semantics remain preserved as unpromoted `LESSON-AIOS-TOOLS-001` rather than mechanically proven exact candidate-head binding.

Phase 5 does not silently adjudicate that lesson or modify CI acceptance semantics.

## Governance freshness

`docs/agent-system/context/governance-lock.yaml` remains valid through `2026-10-04`.

Because the first sync disposition is `MATERIAL_DELTA_PENDING`, freshness was **not renewed**. The repository remains within the existing local-validity window, but a later renewal requires the pending material delta to be separately adjudicated/reconciled or otherwise resolved through governing authority.

## Learning loop

`review/incident/verification finding -> harvest-lesson -> candidate memory -> human/governance adjudication -> smallest promoted rule/test/contract surface OR rejection`

`LESSON-AIOS-TOOLS-001` remains `promotion_state: NONE`. Synchronization can surface its importance but cannot promote it.

## External-fetch triggers

Consult upstream Notion/Drive only when:
1. a requested change would alter global/cross-repository AIOS architecture, memory doctrine, governance, or authority;
2. checked-in authority/context sources conflict or are materially insufficient;
3. the governance lock is expired/stale or declares the local bundle incomplete;
4. the owner explicitly requests upstream synchronization or evidence retrieval.

External retrieval does not itself authorize mutation.

## Direct-main staging

The owner explicitly authorized continued implementation on `main` for this staging sequence. This remains a bounded staging exception and does not erase the repository's normal branch/PR rule for ordinary future work.

## Independent risks carried forward

- `LESSON-AIOS-TOOLS-001`: broader CI exact-candidate binding remains a pending governance delta awaiting separate adjudication;
- branch protection is currently not enabled on `main`;
- capability/network/write authority remains governed independently.

## Next gate

`PHASE_5_VALIDATE_ON_MAIN / MATERIAL_DELTA_PENDING / EXACT_HEAD_LESSON_ADJUDICATION_REQUIRED_BEFORE_FRESHNESS_RENEWAL`.
