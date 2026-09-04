# AIOS-Tools Agent Instructions

## Read order

1. `README.md`
2. `SPEC.md`
3. `docs/agent-system/context/REPOSITORY_HANDOFF.md`
4. `docs/agent-system/context/governance-lock.yaml`
5. `docs/agent-system/knowledge/KNOWLEDGE_INDEX.md`
6. `docs/AUTHORITY_BOUNDARIES.md`
7. the most specific matching `.github/instructions/*.instructions.md` file for touched paths
8. `docs/agent-system/ROLE_AND_SKILL_PROFILE.md` when a reusable procedure or specialist role applies
9. `docs/ARCHITECTURE.md`
10. `docs/DEVELOPMENT.md`
11. `docs/VALIDATION.md`
12. the approved plan or governing contract for the current task

Use checked-in repository context first. Do not fetch Notion or Drive merely to reconstruct ordinary repository context when the local packet is sufficient. External retrieval is reserved for cross-repository/global governance changes, unresolved authority conflicts, an expired/stale local governance lock, or direct owner instruction.

## Repository authority

This repository is authoritative for live implementation and tool-version facts only. Do not invent or revise AIOS architecture, memory doctrine, or global governance here. Those changes require their authoritative upstream path and governed projections.

`docs/AUTHORITY_BOUNDARIES.md` remains the canonical repository authority map. The local agent-system routing layer, Copilot adapter, path instructions, custom agent profiles, skills, and organization auditor are projections/procedures and do not widen repository authority.

## Phase 3 role and skill routing

Repository-native custom agents live under `.github/agents/`. Reusable procedures live under `.github/skills/<skill-name>/SKILL.md`.

Installed skills:
- `plan-feature` — Coordinator planning procedure;
- `review-pr` — Reviewer procedure;
- `verify-head` — Verifier procedure;
- `harvest-lesson` — Knowledge Steward candidate-memory procedure.

`prepare-release` is deferred because no distinct release workflow/Release Steward is established. `sync-governance` remains Phase 5.

Role identity and skill invocation do not grant authority. Reviewer is advisory; Verifier PASS is obligation-local; candidate lessons are not promoted law.

## Phase 4 organization audit

`docs/agent-system/audit/AUDIT_CONTRACT.md` defines the repository-organization obligations enforced by `.github/workflows/repo-governance.yml` through `scripts/agent_system_audit.py`.

The audit checks accepted organization law only: skill/frontmatter integrity, role→skill bindings, department instruction packets, governance freshness, lesson provenance/promotion semantics, public-repo leakage, handoff phase state, and its own exact candidate identity.

`docs/agent-system/context/governance-lock.yaml` expires on its declared `valid_through` date. Expiration fails the organization audit until the repository receives an explicit governance refresh. Phase 5 will automate bounded upstream synchronization; Phase 4 does not.

Unpromoted lesson candidates do not become audit obligations automatically. In particular, `LESSON-AIOS-TOOLS-001` remains candidate memory rather than repository-wide exact-head CI law.

## Change rules

- One coherent concern per branch and pull request.
- Do not commit directly to `main` without a separate, explicit, bounded owner exception.
- Do not rename, delete, or move files without explicit approval.
- Keep the shared core independent from CLI, MCP, and future connector adapters.
- Add tools through the registry, policy, implementation, contracts, and tests as one bounded unit.
- Fail closed for unknown tools, invalid inputs, missing policy, or ambiguous execution eligibility.
- Never claim a check passed unless its command actually ran and evidence is recorded.
- Do not add durable writes, credentials, OAuth, network effects, deployment, or auto-merge without a separately governed plan.
- Review findings may be harvested as lesson candidates, but promotion into rules/tests/contracts requires explicit human/governance adjudication.

## Required validation

```bash
python -m pip install -e ".[dev]"
pytest
aios-tools list
aios-tools invoke system.health --input '{}'
aios-tools-mcp --help
```

Also run any matching department-specific validation required by `.github/instructions/*.instructions.md` and the affected workflow/contract. Changes to the repository operating package must also pass Repository Governance / organization audit.

## Pull-request evidence

Record purpose, governing plan or contract, scope, non-goals, changed files, commands run, observed results, authority impact, security impact, known risks, rollback, and execution-receipt links.
