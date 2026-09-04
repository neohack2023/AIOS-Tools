# AIOS-Tools Agent Adapter Map

State: `PHASE_3_ACTIVE / NATIVE_ADAPTERS_PLUS_SKILLS`

## Canonical semantic entry

All supported agents begin with repository-local context:

1. `AGENTS.md`
2. `docs/agent-system/context/REPOSITORY_HANDOFF.md`
3. `docs/agent-system/knowledge/KNOWLEDGE_INDEX.md`
4. `docs/AUTHORITY_BOUNDARIES.md`
5. the most specific touched-area instruction packet
6. the matching repository-native skill when a stable procedure applies

`.github/copilot-instructions.md` is a thin Copilot adapter. It does not replace `AGENTS.md` or canonical repository documentation.

## Native roles and Phase 3 procedures

- `aios-tools-coordinator` -> `.github/skills/plan-feature/SKILL.md`
- `aios-tools-implementer` -> no distinct skill yet; bounded implementation follows repository law and governing plan
- `aios-tools-reviewer` -> `.github/skills/review-pr/SKILL.md`
- `aios-tools-verifier` -> `.github/skills/verify-head/SKILL.md`
- `aios-tools-knowledge-steward` -> `.github/skills/harvest-lesson/SKILL.md`

Role identity and skill invocation do not grant authority. Review is advisory. Verifier PASS is obligation-local. Merge, release, deploy, capability widening, and global AIOS governance remain separately authorized.

## Path departments

- Browser: `src/aios_tools/browser/**`, browser tests, browser activation replay workflow
- Benchmark: `benchmarks/**`, `src/aios_tools/benchmarks/**`, benchmark registry workflow
- Audio/model: `src/aios_tools/audio_*.py`, dependency-lock and quarantine workflows
- Cartography/web: `apps/cartography-web/**`, `src/aios_tools/cartography/**`
- Execution core/adapters: CLI/MCP, extensions, contracts, policies, and profiles

These are context-routing boundaries, not new ownership or authority stores.

## Learning loop

`review-pr` may identify candidate lessons. `harvest-lesson` may preserve them in `docs/agent-system/lessons/`, but only explicit human/governance adjudication may promote them into common rules, department instructions, tests/workflows, contracts/policies, or documentation.

## Deferred procedures

- `prepare-release`: deferred until a distinct release workflow and role are justified.
- `sync-governance`: Phase 5 only.

## Phase boundary

Phase 3 does not install organization drift auditing or upstream governance synchronization. Those remain Phase 4–5 concerns.
