# AIOS-Tools Agent System

State: `PHASE_3_ACTIVE / LOCAL_CONTEXT_LIVE / NATIVE_ADAPTERS_ACTIVE / NATIVE_SKILLS_ACTIVE / LEARNING_LOOP_CANDIDATE_LANE_ACTIVE`

This directory is the repository-local routing and procedural layer for agent context. It does not replace the repository's existing architecture, authority, development, validation, policy, contract, or security documents.

## Read order for ordinary repository work

1. `../../README.md`
2. `../../SPEC.md`
3. `context/REPOSITORY_HANDOFF.md`
4. `knowledge/KNOWLEDGE_INDEX.md`
5. `../../docs/AUTHORITY_BOUNDARIES.md`
6. the smallest domain-specific repository documents and `.github/instructions/*.instructions.md` packet required for the task
7. `ROLE_AND_SKILL_PROFILE.md` plus the matching `.github/skills/<skill-name>/SKILL.md` when a stable procedure applies
8. the approved plan or governing contract for the current change

## Local-first rule

Use checked-in repository context first. External Notion or Drive retrieval is not part of ordinary bootstrap when the local packet is sufficient. Escalate externally only for cross-repository/global governance changes, unresolved authority conflicts, explicitly stale/incomplete local context, or direct owner instruction.

## Adapter layer

- `.github/copilot-instructions.md` provides a thin repository-wide Copilot router.
- `.github/instructions/*.instructions.md` scopes browser, benchmark, audio/model, cartography/web, and execution-core/adapters context by touched path.
- `.github/agents/*.agent.md` provides bounded Coordinator, Implementer, Reviewer, Verifier, and Knowledge Steward roles.
- `adapters/AGENT_ADAPTER_MAP.md` is the canonical adapter inventory.

## Phase 3 procedures

Canonical project skills live under `.github/skills/`:
- `plan-feature`
- `review-pr`
- `verify-head`
- `harvest-lesson`

`ROLE_AND_SKILL_PROFILE.md` records the adaptive role-to-skill binding. `review/REVIEW_RULES.md` routes review law without duplicating department rules. `lessons/` is a candidate-memory lane; review findings do not become law unless explicitly promoted through a separate governed change.

No skill pre-approves shell/bash execution.

## Authority boundary

GitHub remains authoritative for live implementation, branch, pull-request, commit, CI, and tool-version facts. Existing `docs/AUTHORITY_BOUNDARIES.md` remains the canonical repository authority map. Roles and skills do not grant merge, release, deployment, capability, verifier, or architecture authority.

## Phase map

- Phase 0: adaptation profile complete.
- Phase 1: local context bundle and semantic handoff live on main.
- Phase 2: tool/agent adapters and scoped departments live on main.
- Phase 3: four repository-native skills and candidate learning loop live on main.
- Phase 4: organization drift audit, not installed.
- Phase 5: bounded upstream governance synchronization, not installed.
