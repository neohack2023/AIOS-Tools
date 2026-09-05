# AIOS-Tools Agent System

State: `PHASE_5_ACTIVE / PHASE_5_COMPLETE / SELF_SUFFICIENT_REPO_ACTIVE / LOCAL_CONTEXT_LIVE / NATIVE_ADAPTERS_ACTIVE / NATIVE_SKILLS_ACTIVE / LEARNING_LOOP_ACTIVE / ORGANIZATION_AUDIT_ACTIVE / GOVERNANCE_SYNC_ACTIVE`

This directory is the repository-local routing, procedural, self-audit, and bounded-governance-sync layer for agent context. It does not replace the repository's existing architecture, authority, development, validation, policy, contract, or security documents.

## Read order for ordinary repository work

1. `../../README.md`
2. `../../SPEC.md`
3. `context/REPOSITORY_HANDOFF.md`
4. `context/governance-lock.yaml`
5. `knowledge/KNOWLEDGE_INDEX.md`
6. `../../docs/AUTHORITY_BOUNDARIES.md`
7. the smallest domain-specific repository documents and `.github/instructions/*.instructions.md` packet required for the task
8. `ROLE_AND_SKILL_PROFILE.md` plus the matching `.github/skills/<skill-name>/SKILL.md` when a stable procedure applies
9. the approved plan or governing contract for the current change

## Local-first rule

Use checked-in repository context first. External Notion or Drive retrieval is not part of ordinary bootstrap when the local packet is sufficient. Escalate externally only for cross-repository/global governance changes, unresolved authority conflicts, an expired/stale governance lock, or direct owner instruction.

## Adapter layer

- `.github/copilot-instructions.md` provides a thin repository-wide Copilot router.
- `.github/instructions/*.instructions.md` scopes browser, benchmark, audio/model, cartography/web, and execution-core/adapters context by touched path.
- `.github/agents/*.agent.md` provides bounded Coordinator, Implementer, Reviewer, Verifier, and Knowledge Steward roles.
- `adapters/AGENT_ADAPTER_MAP.md` is the canonical adapter inventory.

## Repository-native procedures

Canonical project skills live under `.github/skills/`:
- `plan-feature`
- `review-pr`
- `verify-head`
- `harvest-lesson`
- `sync-governance`

`ROLE_AND_SKILL_PROFILE.md` records the adaptive role-to-skill binding. `review/REVIEW_RULES.md` routes review law without duplicating department rules. `lessons/` is a candidate-memory lane; review findings do not become law unless explicitly promoted through a separate governed change.

No skill pre-approves shell/bash execution. `prepare-release` remains deferred because no distinct release lane is established.

## Phase 4/5 verification architecture

- `audit/AUDIT_CONTRACT.md` defines accepted target-specific audit obligations.
- `scripts/agent_system_audit.py` is the organization-audit foundation.
- `scripts/agent_system_audit_phase5.py` composes Phase 5 skill/lock/handoff/sync expectations.
- `scripts/ci_exact_head_audit.py` owns only AIOS-specific Actions trust-binding policy.
- actionlint owns generic GitHub Actions syntax/semantics.
- blocking zizmor owns generic GitHub Actions security/supply-chain evidence.
- `.github/workflows/repo-governance.yml` remains the mechanical owner and uploads exact-head receipts.

The audit checks accepted organization law only. Candidate lessons remain non-binding until promoted through governance.

## Phase 5 governance synchronization

- `governance-sync/UPSTREAM_SYNC_PROFILE.md` pins the target-specific stable upstream authority set.
- `.github/skills/sync-governance/SKILL.md` is the Knowledge Steward procedure.
- `governance-sync/receipts/*.json` preserves immutable source identities, observed versions, deltas, and freshness decisions.
- `scripts/governance_sync.py` validates receipt digest/source-set/freshness/authority semantics.
- `tests/test_governance_sync.py` exercises fail-closed behavior.

Receipt `GSYNC-AIOS-TOOLS-20260904-001` remains historical `MATERIAL_DELTA_PENDING` evidence. Receipt `GSYNC-AIOS-TOOLS-20260904-002` is the terminal post-repair comparison with `MATERIAL_DELTA_RECONCILED` and freshness renewal applied. `valid_through` remains `2026-10-04` because both syncs occur on the same local date and the freshness window is 30 days.

## Authority boundary

GitHub remains authoritative for live implementation, branch, pull-request, commit, CI, and tool-version facts. Existing `docs/AUTHORITY_BOUNDARIES.md` remains the canonical repository authority map. Roles, skills, audit results, sync results, and CI do not grant merge, release, deployment, capability, verifier, mutation, or architecture authority.

## Phase map

- Phase 0: adaptation profile complete.
- Phase 1: local context bundle and semantic handoff live.
- Phase 2: tool/agent adapters and scoped departments live.
- Phase 3: adaptive repository-native skills and candidate learning loop live.
- Phase 4: adaptive organization audit and governance freshness live.
- Phase 5: **complete**. Bounded upstream synchronization is active, the exact-head material delta is reconciled, freshness renewal is mechanically permitted/applied, and ordinary repository work remains external-fetch-free.

Terminal state: `AIOS_TOOLS_PHASE_5 / SELF_SUFFICIENT_REPO_ACTIVE / UPSTREAM_SYNC_ACTIVE / MATERIAL_DELTA_RECONCILED / FRESHNESS_RENEWED / NORMAL_REPO_WORK_EXTERNAL_FETCH_REQUIRED_FALSE / GOVERNANCE_VALID_THROUGH_2026-10-04`.
