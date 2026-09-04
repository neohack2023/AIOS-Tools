# AIOS-Tools Agent Instructions

## Read order

1. `README.md`
2. `SPEC.md`
3. `docs/agent-system/context/REPOSITORY_HANDOFF.md`
4. `docs/agent-system/knowledge/KNOWLEDGE_INDEX.md`
5. `docs/AUTHORITY_BOUNDARIES.md`
6. the most specific matching `.github/instructions/*.instructions.md` file for touched paths
7. `docs/ARCHITECTURE.md`
8. `docs/DEVELOPMENT.md`
9. `docs/VALIDATION.md`
10. the approved plan or governing contract for the current task

Use checked-in repository context first. Do not fetch Notion or Drive merely to reconstruct ordinary repository context when the local packet is sufficient. External retrieval is reserved for cross-repository/global governance changes, unresolved authority conflicts, explicitly stale or incomplete local context, or direct owner instruction.

## Repository authority

This repository is authoritative for live implementation and tool-version facts only. Do not invent or revise AIOS architecture, memory doctrine, or governance here. Those changes require their authoritative Notion path and governed Drive projections.

`docs/AUTHORITY_BOUNDARIES.md` remains the canonical repository authority map. The local agent-system routing layer, Copilot adapter, path instructions, and custom agent profiles are projections and do not widen repository authority.

## Phase 2 agent routing

Repository-native custom agents live under `.github/agents/`. Their role identity limits behavior but does not grant authority. Reviewer is advisory; Verifier PASS is obligation-local; Coordinator routes; Implementer implements bounded changes; Knowledge Steward maintains local routing.

`docs/agent-system/adapters/AGENT_ADAPTER_MAP.md` is the adapter inventory. Phase 3 skills and learning-loop machinery are not installed yet.

## Change rules

- One coherent concern per branch and pull request.
- Do not commit directly to `main` without a separate, explicit, bounded owner exception.
- Do not rename, delete, or move files without explicit approval.
- Keep the shared core independent from CLI, MCP, and future connector adapters.
- Add tools through the registry, policy, implementation, contracts, and tests as one bounded unit.
- Fail closed for unknown tools, invalid inputs, missing policy, or ambiguous execution eligibility.
- Never claim a check passed unless its command actually ran and evidence is recorded.
- Do not add durable writes, credentials, OAuth, network effects, deployment, or auto-merge without a separately governed plan.

## Required validation

```bash
python -m pip install -e ".[dev]"
pytest
aios-tools list
aios-tools invoke system.health --input '{}'
aios-tools-mcp --help
```

Also run any matching department-specific validation required by `.github/instructions/*.instructions.md` and the affected workflow/contract.

## Pull-request evidence

Record purpose, governing plan or contract, scope, non-goals, changed files, commands run, observed results, authority impact, security impact, known risks, rollback, and execution-receipt links.
