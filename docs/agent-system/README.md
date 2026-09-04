# AIOS-Tools Agent System

State: `PHASE_1_CANDIDATE / LOCAL_CONTEXT_ROUTER_ACTIVE_ON_BRANCH / NO_PHASE_2_ADAPTERS`

This directory is the repository-local routing layer for agent context. It does not replace the repository's existing architecture, authority, development, validation, policy, contract, or security documents.

## Read order for ordinary repository work

1. `../../README.md`
2. `../../SPEC.md`
3. `context/REPOSITORY_HANDOFF.md`
4. `knowledge/KNOWLEDGE_INDEX.md`
5. `../../docs/AUTHORITY_BOUNDARIES.md`
6. the smallest domain-specific repository documents required for the task
7. the approved plan or governing contract for the current change

## Phase 1 rule

Use checked-in repository context first. External Notion or Drive retrieval is not part of ordinary bootstrap when the local packet is sufficient. Escalate externally only for cross-repository/global governance changes, unresolved authority conflicts, explicitly stale/incomplete local context, or direct owner instruction.

## Authority boundary

GitHub remains authoritative for live implementation, branch, pull-request, commit, CI, and tool-version facts. Existing `docs/AUTHORITY_BOUNDARIES.md` remains the canonical repository authority map. This router does not grant merge, release, deployment, capability, verifier, or architecture authority.

## Phase map

- Phase 0: adaptation profile complete.
- Phase 1: local context bundle and semantic handoff, this candidate.
- Phase 2: tool/agent adapters, not installed.
- Phase 3: repository-native skills, not installed.
- Phase 4: organization drift audit, not installed.
- Phase 5: bounded upstream governance synchronization, not installed.
