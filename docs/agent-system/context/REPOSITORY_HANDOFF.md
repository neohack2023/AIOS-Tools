# AIOS-Tools Repository Handoff

State: `PHASE_5_ACTIVE / LOCAL_CONTEXT_LIVE / NATIVE_AGENT_ADAPTERS_ACTIVE / NATIVE_SKILLS_ACTIVE / LEARNING_LOOP_ACTIVE / ORGANIZATION_AUDIT_ACTIVE / GOVERNANCE_SYNC_ACTIVE / EXACT_HEAD_REPAIR_CANDIDATE_ACTIVE`

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

Resolve current mutable branch/head/PR/CI facts live from GitHub. Historical SHAs above are provenance anchors, not timeless claims about current `main`.

## Mission

AIOS-Tools is the governed capability and execution layer for AIOS. It provides the shared Python core plus CLI, MCP, browser, benchmark, cartography/web, and connector/tool surfaces while preserving fail-closed policy and evidence boundaries.

## Current operating model

Phase 1 made ordinary bootstrap local-first. Phase 2 added native roles and path departments. Phase 3 added reusable procedures and a candidate learning loop. Phase 4 added deterministic self-audit. Phase 5 added a bounded resupply path without restoring ambient Notion/Drive dependence.

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

Historical receipt disposition: `MATERIAL_DELTA_PENDING`.

- Reconciled in the receipt: upstream branch/PR default versus explicit owner-authorized direct-main staging episodes. Local repository law still makes branch/PR delivery the default; staging exceptions are bounded and non-reusable.
- Material delta identified by the receipt: verifier-owned acceptance requires exact artifact/head identity for acceptance-owning evidence.

That delta has now been explicitly adjudicated. `LESSON-AIOS-TOOLS-001` is promoted on PR #59 and the repair candidate binds acceptance-relevant PR workflows to the exact candidate head, verifies checkout identity, audits the binding structurally, and fails closed on unsupported trigger syntax or non-enforcing identity checks.

The original sync receipt remains historically `MATERIAL_DELTA_PENDING` because receipts are immutable. Until PR #59 is promoted to `main` and a new governance-sync receipt reclassifies the comparison, the governance lock remains pending and freshness remains unrenewed.

## Governance freshness

`docs/agent-system/context/governance-lock.yaml` remains valid through `2026-10-04`.

The first sync did not renew freshness. PR #59 is a repair candidate, not a freshness receipt. A later renewal requires promotion of the repair and a new mechanically valid governance-sync receipt with an allowed disposition.

## Learning loop

`review/incident/verification finding -> harvest-lesson -> candidate memory -> human/governance adjudication -> smallest promoted rule/test/contract surface OR rejection`

`LESSON-AIOS-TOOLS-001` is now `promotion_state: PROMOTED` on the repair branch after explicit owner/governance adjudication. Its promotion target is the exact-head workflow/audit contract. Promotion remains obligation-scoped and grants no merge/release/deploy/capability authority.

## External-fetch triggers

Consult upstream Notion/Drive only when:
1. a requested change would alter global/cross-repository AIOS architecture, memory doctrine, governance, or authority;
2. checked-in authority/context sources conflict or are materially insufficient;
3. the governance lock is expired/stale or declares the local bundle incomplete;
4. the owner explicitly requests upstream synchronization or evidence retrieval.

External retrieval does not itself authorize mutation.

## Direct-main staging

The earlier owner-authorized direct-main staging sequence is complete. Normal future work follows branch/PR delivery unless a new explicit bounded exception is granted.

## Independent risks carried forward

- PR #59 exact-head repair must be reviewed and verified on its current head before merge authorization can be exercised;
- the historical first sync receipt remains `MATERIAL_DELTA_PENDING` until a post-promotion resynchronization reclassifies it;
- branch protection is currently not enabled on `main`;
- capability/network/write authority remains governed independently.

## Next gate

`PR_59_CURRENT_HEAD_FULL_REVIEW / EXACT_HEAD_CI / OWNER_EXACT_HEAD_MERGE_AUTHORIZATION / POST_MERGE_GOVERNANCE_RESYNC`
