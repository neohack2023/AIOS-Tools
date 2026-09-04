# AIOS-Tools Local Context Bundle

State: `PHASE_5_ACTIVE / LOCAL_FIRST / GOVERNANCE_SYNC_BOUNDED`

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
- `docs/agent-system/context/governance-lock.yaml`
- `docs/agent-system/knowledge/KNOWLEDGE_INDEX.md`
- `docs/agent-system/ROLE_AND_SKILL_PROFILE.md`

### Repository-native procedures and audit
- `.github/skills/`
- `.github/agents/`
- `.github/instructions/`
- `docs/agent-system/review/REVIEW_RULES.md`
- `docs/agent-system/lessons/CANDIDATES.md`
- `docs/agent-system/audit/AUDIT_CONTRACT.md`
- `scripts/agent_system_audit_phase5.py`
- `scripts/ci_exact_head_audit.py`
- `scripts/governance_sync.py`

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

Load the smallest relevant subset. Do not pull every document, workflow, fixture, policy, lesson, or skill into context by default.

For a normal bounded implementation task, begin with repository identity, semantic handoff, governance lock, knowledge index, authority boundaries, and the task-specific implementation/validation files. Then read the exact policy/contract/tests for the affected domain.

## What this bundle does not do

It does not duplicate Notion governance, copy Drive evidence archives, authorize capabilities, define a new verifier, or make local documentation superior to explicit upstream authority where the repository declares that authority upstream.

## Upstream escalation and synchronization

Phase 5 replaces ambient external-memory bootstrap with a bounded Knowledge Steward resupply path. Use the triggers in `REPOSITORY_HANDOFF.md` and the pinned source set in `docs/agent-system/governance-sync/UPSTREAM_SYNC_PROFILE.md`.

A successful external fetch is not a successful synchronization and cannot extend freshness. Only a mechanically valid sync receipt with an allowed disposition may renew `valid_through`.

Normal repository work remains local-first and external-fetch-free unless a declared escalation/sync trigger applies.
