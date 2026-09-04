# AIOS-Tools Repository Handoff

State: `PHASE_1_CANDIDATE / SEMANTIC_HANDOFF_ACTIVE_ON_BRANCH`

## Repository identity

- Repository: `neohack2023/AIOS-Tools`
- Default branch: `main`
- Phase 0 profile commit: `1550dcb6a5b39ed79f41bb6d124736b2b72c2871`
- Frozen Phase 0 input head: `a8b47f74f0d2f7e6bcfaf25399ebc5ce7dd48e20`
- Phase 1 candidate branch: `aios/repo-autonomy-phase-1`

Resolve current mutable branch/head/PR/CI facts live from GitHub. Historical SHAs above identify the Phase 0 input and Phase 1 base only.

## Mission

AIOS-Tools is the governed capability and execution layer for AIOS. It provides the shared Python core plus CLI, MCP, browser, benchmark, cartography/web, and future connector/tool surfaces while preserving fail-closed policy and evidence boundaries.

## Current operating model

Repository-local files already carry substantial operating context. Phase 1 therefore reuses rather than duplicates:

- `AGENTS.md` for repository agent law and validation order;
- `SPEC.md` for implementation scope;
- `docs/ARCHITECTURE.md` for system structure;
- `docs/AUTHORITY_BOUNDARIES.md` for repository/upstream authority separation;
- `docs/DEVELOPMENT.md` for development rules;
- `docs/VALIDATION.md` for verification obligations;
- `CONTRIBUTING.md`, `SECURITY.md`, and `.github/pull_request_template.md` for contribution/security/review evidence.

## Active verification surfaces

- `.github/workflows/ci.yml`: Linux, Windows, browser-core, and cartography-web lanes.
- `.github/workflows/repo-governance.yml`: required repository surfaces, authority markers, Python compile check.
- additional bounded workflows cover benchmark registry, browser replay, audio-model dependency locking, and model quarantine.

## Current Phase 1 objective

Make ordinary repository bootstrap local-first by adding a semantic handoff and knowledge router around the repository's existing canonical documents. Do not install Phase 2 adapters, Phase 3 skills, Phase 4 audit machinery, or Phase 5 governance synchronization in this phase.

## External-fetch triggers

Consult upstream Notion/Drive only when one of these conditions is true:

1. a requested change would alter global/cross-repository AIOS architecture, memory doctrine, governance, or authority;
2. checked-in authority/context sources conflict or are insufficient to resolve a material decision;
3. a future repository governance lock explicitly declares the local bundle stale or incomplete;
4. the owner explicitly requests upstream synchronization or evidence retrieval.

External retrieval does not itself authorize a repository mutation.

## Independent risks carried forward

- existing CI checkouts are not yet mechanically bound to an immutable PR candidate head;
- branch protection is currently not enabled on `main`;
- repository self-sufficiency audit and governance freshness mechanics are not yet installed;
- capability/network/write authority remains governed independently of this documentation layer.

## Next gate

`PHASE_1_REVIEW_AND_VALIDATION` before any Phase 2 adapter work.
