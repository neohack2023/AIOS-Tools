# AIOS-Tools Repository Handoff

State: `PHASE_4_ACTIVE / LOCAL_CONTEXT_LIVE / NATIVE_AGENT_ADAPTERS_ACTIVE / NATIVE_SKILLS_ACTIVE / LEARNING_LOOP_ACTIVE / ORGANIZATION_AUDIT_ACTIVE`

## Repository identity

- Repository: `neohack2023/AIOS-Tools`
- Default branch: `main`
- Frozen Phase 0 input head: `a8b47f74f0d2f7e6bcfaf25399ebc5ce7dd48e20`
- Phase 0 profile commit: `1550dcb6a5b39ed79f41bb6d124736b2b72c2871`
- Phase 1 staged head: `335c4e31c53ef3a2f8e4612fa60a7d13178e61ec`
- Phase 2 staged head: `6c5228d49c297b8268eb761e1e0f250245b57c52`
- Phase 3 staged head: `0c339033368b4d26c448041ad03900142d05ba73`

Resolve current mutable branch/head/PR/CI facts live from GitHub. Historical SHAs above are provenance anchors, not timeless claims about current `main`.

## Mission

AIOS-Tools is the governed capability and execution layer for AIOS. It provides the shared Python core plus CLI, MCP, browser, benchmark, cartography/web, and connector/tool surfaces while preserving fail-closed policy and evidence boundaries.

## Current operating model

Phase 1 made ordinary bootstrap local-first. Phase 2 added native roles and path departments. Phase 3 added reusable procedures and a candidate learning loop. Phase 4 adds deterministic self-audit without duplicating the existing governance workflow:

- `.github/workflows/repo-governance.yml` remains the owning repository-governance workflow;
- `scripts/agent_system_audit.py` validates the accepted organization contract;
- `tests/test_agent_system_audit.py` exercises critical auditor failure modes;
- `docs/agent-system/audit/AUDIT_CONTRACT.md` defines the audit obligation;
- `docs/agent-system/context/governance-lock.yaml` makes freshness explicit and fail-closed after its `valid_through` date;
- audit output is `outputs/agent-system-audit.json` and is uploaded as workflow evidence.

The workflow binds its own checkout/evidence to the exact candidate SHA. This does not silently promote the broader repository exact-head lesson into law.

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
- Implementer -> no distinct skill yet; follows repository law + touched-area packet + governing plan

Role identity and skill invocation do not grant merge, release, deploy, capability, verifier-class, or global-governance authority.

## Learning loop

`review/incident/verification finding -> harvest-lesson -> candidate memory -> human/governance adjudication -> smallest promoted rule/test/contract surface OR rejection`

Candidate lessons are not enforceable until explicitly promoted. `LESSON-AIOS-TOOLS-001` remains `promotion_state: NONE`; Phase 4 audits its provenance/promotion semantics but does not promote or enforce its proposed repository-wide exact-head invariant.

## Governance freshness

`docs/agent-system/context/governance-lock.yaml` is valid through `2026-10-04`. After that date, Repository Governance fails closed until the local governance snapshot is explicitly refreshed. Phase 5 will define the bounded upstream-sync source set and receipt-bound renewal procedure.

## External-fetch triggers

Consult upstream Notion/Drive only when:

1. a requested change would alter global/cross-repository AIOS architecture, memory doctrine, governance, or authority;
2. checked-in authority/context sources conflict or are materially insufficient;
3. the governance lock is expired/stale or later declares the local bundle incomplete;
4. the owner explicitly requests upstream synchronization or evidence retrieval.

External retrieval does not itself authorize mutation.

## Direct-main staging

The owner explicitly authorized continued implementation on `main` for this staging sequence. This remains a bounded staging exception and does not erase the repository's normal branch/PR rule for ordinary future work.

## Independent risks carried forward

- broader repository CI checkouts are not yet uniformly bound to immutable PR candidate heads; preserved as unpromoted `LESSON-AIOS-TOOLS-001`;
- branch protection is currently not enabled on `main`;
- Phase 5 upstream governance synchronization is not installed;
- capability/network/write authority remains governed independently.

## Next gate

`PHASE_4_VALIDATE_ON_MAIN / PHASE_5_NOT_YET_AUTHORIZED`.
