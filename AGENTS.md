# AIOS-Tools Agent Instructions

## Read order

1. `README.md`
2. `SPEC.md`
3. `docs/AUTHORITY_BOUNDARIES.md`
4. `docs/ARCHITECTURE.md`
5. `docs/DEVELOPMENT.md`
6. `docs/VALIDATION.md`
7. the approved plan for the current task

## Repository authority

This repository is authoritative for live implementation and tool-version facts only. Do not invent or revise AIOS architecture, memory doctrine, or governance here. Those changes require their authoritative Notion path and governed Drive projections.

## Change rules

- One coherent concern per branch and pull request.
- Do not commit directly to `main`.
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

## Pull-request evidence

Record purpose, governing plan or contract, scope, non-goals, changed files, commands run, observed results, authority impact, security impact, known risks, rollback, and execution-receipt links.