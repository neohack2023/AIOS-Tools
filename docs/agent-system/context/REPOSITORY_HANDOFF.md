# AIOS-Tools Repository Handoff

State: `PHASE_2_ACTIVE / LOCAL_CONTEXT_LIVE / NATIVE_AGENT_ADAPTERS_ACTIVE`

## Repository identity

- Repository: `neohack2023/AIOS-Tools`
- Default branch: `main`
- Frozen Phase 0 input head: `a8b47f74f0d2f7e6bcfaf25399ebc5ce7dd48e20`
- Phase 0 profile commit: `1550dcb6a5b39ed79f41bb6d124736b2b72c2871`
- Phase 1 staged head: `335c4e31c53ef3a2f8e4612fa60a7d13178e61ec`

Resolve current mutable branch/head/PR/CI facts live from GitHub. Historical SHAs above are provenance anchors, not timeless claims about current `main`.

## Mission

AIOS-Tools is the governed capability and execution layer for AIOS. It provides the shared Python core plus CLI, MCP, browser, benchmark, cartography/web, and connector/tool surfaces while preserving fail-closed policy and evidence boundaries.

## Current operating model

Phase 1 made ordinary bootstrap local-first. Phase 2 adds native routing without duplicating doctrine:

- `AGENTS.md` remains repository operating law;
- `.github/copilot-instructions.md` routes Copilot into the same local packet;
- `.github/instructions/*.instructions.md` applies scoped department context to touched paths;
- `.github/agents/*.agent.md` supplies five bounded specialist roles;
- `docs/agent-system/adapters/AGENT_ADAPTER_MAP.md` records role and department routing.

Canonical authority, architecture, development, validation, security, contract, policy, fixture, and test surfaces remain where they already lived.

## Phase 2 departments

1. browser capability;
2. benchmark registry;
3. audio/model dependency and quarantine;
4. cartography/web;
5. shared execution core and adapters.

These are context-routing boundaries, not ownership or authorization stores.

## Agent roles

- Coordinator: scope and route only.
- Implementer: bounded implementation only.
- Reviewer: read-only advisory review.
- Verifier: execute declared checks; no implementation edits.
- Knowledge Steward: maintain local semantic routing.

Role identity does not grant merge, release, deploy, capability, verifier-class, or global-governance authority.

## External-fetch triggers

Consult upstream Notion/Drive only when:

1. a requested change would alter global/cross-repository AIOS architecture, memory doctrine, governance, or authority;
2. checked-in authority/context sources conflict or are materially insufficient;
3. a future governance lock declares the local bundle stale or incomplete;
4. the owner explicitly requests upstream synchronization or evidence retrieval.

External retrieval does not itself authorize mutation.

## Independent risks carried forward

- existing CI checkouts are not yet mechanically bound to an immutable PR candidate head;
- branch protection is currently not enabled on `main`;
- repository-native skills and review-learning loop are not yet installed;
- repository self-audit and governance freshness mechanics are not yet installed;
- capability/network/write authority remains governed independently.

## Next gate

`PHASE_2_VALIDATE_ON_MAIN / PHASE_3_NOT_YET_AUTHORIZED`.
