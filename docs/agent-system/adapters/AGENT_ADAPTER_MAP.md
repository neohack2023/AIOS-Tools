# AIOS-Tools Agent Adapter Map

State: `PHASE_2_ACTIVE`

## Canonical semantic entry

All supported agents begin with repository-local context:

1. `AGENTS.md`
2. `docs/agent-system/context/REPOSITORY_HANDOFF.md`
3. `docs/agent-system/knowledge/KNOWLEDGE_INDEX.md`
4. `docs/AUTHORITY_BOUNDARIES.md`
5. the most specific touched-area instruction packet

`.github/copilot-instructions.md` is a thin Copilot adapter. It does not replace `AGENTS.md` or canonical repository documentation.

## Native roles

- `aios-tools-coordinator` — route and scope only
- `aios-tools-implementer` — bounded implementation
- `aios-tools-reviewer` — read-only advisory review
- `aios-tools-verifier` — obligation-local mechanical verification
- `aios-tools-knowledge-steward` — local semantic routing maintenance

Role identity does not grant authority. Review is advisory. Verifier PASS is obligation-local. Merge, release, deploy, capability widening, and global AIOS governance remain separately authorized.

## Path departments

- Browser: `src/aios_tools/browser/**`, browser tests, browser activation replay workflow
- Benchmark: `benchmarks/**`, `src/aios_tools/benchmarks/**`, benchmark registry workflow
- Audio/model: `src/aios_tools/audio_*.py`, dependency-lock and quarantine workflows
- Cartography/web: `apps/cartography-web/**`, `src/aios_tools/cartography/**`
- Execution core/adapters: CLI/MCP, extensions, contracts, policies, and profiles

These are context-routing boundaries, not new ownership or authority stores.

## Phase boundary

Phase 2 does not install repository-native `SKILL.md` procedures, PR-rule promotion, anti-pattern harvesting, organization drift auditing, or upstream governance synchronization. Those remain Phase 3–5 concerns.
