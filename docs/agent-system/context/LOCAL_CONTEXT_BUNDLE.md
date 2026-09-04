# AIOS-Tools Local Context Bundle

State: `PHASE_1_CANDIDATE`

This bundle defines what an agent should load locally before reaching outside the repository.

## Canonical local sources

### Identity and scope
- `README.md`
- `SPEC.md`

### Authority and architecture
- `docs/AUTHORITY_BOUNDARIES.md`
- `docs/ARCHITECTURE.md`

### Development and validation
- `docs/DEVELOPMENT.md`
- `docs/VALIDATION.md`
- `CONTRIBUTING.md`
- `SECURITY.md`
- `.github/pull_request_template.md`

### Agent routing
- `AGENTS.md`
- `docs/REPO_ADAPTATION_PROFILE.md`
- `docs/agent-system/context/REPOSITORY_HANDOFF.md`
- `docs/agent-system/knowledge/KNOWLEDGE_INDEX.md`

### Executable repository truth
- `src/`
- `contracts/`
- `policies/`
- `fixtures/`
- `benchmarks/`
- `profiles/`
- `extensions/`
- `apps/`
- `.github/workflows/`

## Loading rule

Load the smallest relevant subset. Do not pull every document, workflow, fixture, or policy into context by default.

For a normal bounded implementation task, begin with repository identity, semantic handoff, knowledge index, authority boundaries, and the task-specific implementation/validation files. Then read the exact policy/contract/tests for the affected domain.

## What this bundle does not do

It does not duplicate Notion governance, copy Drive evidence archives, authorize capabilities, define a new verifier, or make local documentation superior to explicit upstream authority where the repository declares that authority upstream.

## Upstream escalation

Use the triggers in `REPOSITORY_HANDOFF.md`. Until Phase 5 exists, upstream synchronization is manual and governed; this Phase 1 bundle only reduces unnecessary bootstrap retrieval.
