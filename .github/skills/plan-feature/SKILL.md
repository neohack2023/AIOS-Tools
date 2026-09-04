---
name: plan-feature
description: Produce a bounded AIOS-Tools implementation plan from repository-local context. Use for material feature, capability, policy, workflow, or cross-department changes before implementation.
---

# Plan Feature

Use this procedure to turn a requested AIOS-Tools change into a bounded implementation plan. Planning does not authorize implementation.

## Load
1. `AGENTS.md`.
2. `docs/agent-system/context/REPOSITORY_HANDOFF.md`.
3. `docs/agent-system/knowledge/KNOWLEDGE_INDEX.md`.
4. `docs/AUTHORITY_BOUNDARIES.md`.
5. The most specific `.github/instructions/*.instructions.md` packets for affected paths.
6. Relevant contracts, policies, fixtures, tests, workflows, and governing plan/contract.

Use checked-in context first. Fetch Notion/Drive only when an explicit external-fetch trigger applies.

## Produce
State:
- objective and non-goals;
- affected departments and paths;
- authority boundary;
- exact live base/head identity when relevant;
- contracts/policies/fixtures/tests/workflows that constrain the change;
- implementation slices in dependency order;
- verifier obligations for each material slice;
- rollback/recovery path;
- unresolved decisions requiring owner or upstream governance input.

## Stop conditions
Stop and escalate instead of widening scope when:
- repository-local authority conflicts with upstream/global AIOS law;
- the requested change requires credentials, durable external writes, release/deploy, or capability widening without separate authorization;
- acceptance cannot be defined mechanically enough for the affected obligation.

`PLAN != AUTHORIZATION` and `ROLE != AUTHORITY`.
