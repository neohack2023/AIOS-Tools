# AIOS-Tools Repository Handoff

State: `PHASE_3_ACTIVE / LOCAL_CONTEXT_LIVE / NATIVE_AGENT_ADAPTERS_ACTIVE / NATIVE_SKILLS_ACTIVE / LEARNING_LOOP_CANDIDATE_LANE_ACTIVE`

## Repository identity

- Repository: `neohack2023/AIOS-Tools`
- Default branch: `main`
- Frozen Phase 0 input head: `a8b47f74f0d2f7e6bcfaf25399ebc5ce7dd48e20`
- Phase 0 profile commit: `1550dcb6a5b39ed79f41bb6d124736b2b72c2871`
- Phase 1 staged head: `335c4e31c53ef3a2f8e4612fa60a7d13178e61ec`
- Phase 2 staged head: `6c5228d49c297b8268eb761e1e0f250245b57c52`

Resolve current mutable branch/head/PR/CI facts live from GitHub. Historical SHAs above are provenance anchors, not timeless claims about current `main`.

## Mission

AIOS-Tools is the governed capability and execution layer for AIOS. It provides the shared Python core plus CLI, MCP, browser, benchmark, cartography/web, and connector/tool surfaces while preserving fail-closed policy and evidence boundaries.

## Current operating model

Phase 1 made ordinary bootstrap local-first. Phase 2 added native roles and path departments. Phase 3 adds reusable procedures without duplicating doctrine:

- `.github/skills/plan-feature/SKILL.md`
- `.github/skills/review-pr/SKILL.md`
- `.github/skills/verify-head/SKILL.md`
- `.github/skills/harvest-lesson/SKILL.md`
- `docs/agent-system/ROLE_AND_SKILL_PROFILE.md`
- `docs/agent-system/review/REVIEW_RULES.md`
- `docs/agent-system/lessons/README.md`
- `docs/agent-system/lessons/CANDIDATES.md`

`prepare-release` is deferred because no distinct release workflow/Release Steward is established. `sync-governance` remains Phase 5.

## Phase 2 departments

1. browser capability;
2. benchmark registry;
3. audio/model dependency and quarantine;
4. cartography/web;
5. shared execution core and adapters.

These are context-routing boundaries, not ownership or authorization stores.

## Agent/skill binding

- Coordinator -> `plan-feature`
- Reviewer -> `review-pr`
- Verifier -> `verify-head`
- Knowledge Steward -> `harvest-lesson`
- Implementer -> no distinct skill yet; follows repository law + touched-area packet + governing plan

Role identity and skill invocation do not grant merge, release, deploy, capability, verifier-class, or global-governance authority.

## Learning loop

`review/incident/verification finding -> harvest-lesson -> candidate memory -> human/governance adjudication -> smallest promoted rule/test/contract surface OR rejection`

Candidate lessons are not enforceable until explicitly promoted. Phase 3 seeds `LESSON-AIOS-TOOLS-001` from the Phase 0 exact-head evidence-binding risk with promotion state `NONE`.

## External-fetch triggers

Consult upstream Notion/Drive only when:

1. a requested change would alter global/cross-repository AIOS architecture, memory doctrine, governance, or authority;
2. checked-in authority/context sources conflict or are materially insufficient;
3. a future governance lock declares the local bundle stale or incomplete;
4. the owner explicitly requests upstream synchronization or evidence retrieval.

External retrieval does not itself authorize mutation.

## Direct-main staging

The owner explicitly authorized continuation on `main` for this Phase 3 staging episode. This is a bounded, non-reusable exception; normal branch/PR delivery remains the default unless separately authorized.

## Independent risks carried forward

- existing CI checkouts are not yet mechanically bound to an immutable PR candidate head; preserved as `LESSON-AIOS-TOOLS-001`, not yet promoted law;
- branch protection is currently not enabled on `main`;
- repository self-audit and governance freshness mechanics are not yet installed;
- capability/network/write authority remains governed independently.

## Next gate

`PHASE_3_VALIDATE_ON_MAIN / PHASE_4_NOT_YET_AUTHORIZED`.
