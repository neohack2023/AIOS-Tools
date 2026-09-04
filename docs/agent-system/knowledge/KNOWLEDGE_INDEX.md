# AIOS-Tools Knowledge Index

State: `PHASE_3_ACTIVE`

Use this index to route questions to the smallest authoritative repository surface.

## Repository identity and operating law
- `README.md` — product/repository identity and user-facing operation.
- `SPEC.md` — implementation scope and constraints.
- `AGENTS.md` — repository agent instructions.
- `.github/copilot-instructions.md` — thin Copilot adapter into canonical local context.
- `docs/AUTHORITY_BOUNDARIES.md` — GitHub vs upstream Notion/Drive authority.
- `docs/REPO_ADAPTATION_PROFILE.md` — Phase 0 repository-specific rollout decisions.
- `docs/agent-system/adapters/AGENT_ADAPTER_MAP.md` — role and department routing.
- `docs/agent-system/ROLE_AND_SKILL_PROFILE.md` — Phase 3 adaptive role/skill binding.

## Repository-native procedures
- `.github/skills/plan-feature/SKILL.md`
- `.github/skills/review-pr/SKILL.md`
- `.github/skills/verify-head/SKILL.md`
- `.github/skills/harvest-lesson/SKILL.md`
- Review router: `docs/agent-system/review/REVIEW_RULES.md`.
- Candidate institutional memory: `docs/agent-system/lessons/README.md` and `docs/agent-system/lessons/CANDIDATES.md`.

## Shared capability and execution core
- `src/aios_tools/` — live Python implementation.
- `contracts/` — machine-facing contracts and schemas.
- `policies/` — execution/policy constraints.
- `fixtures/` — deterministic fixtures and bounded evidence inputs.
- `profiles/` — bounded runtime/profile configuration.
- `tests/` — executable regression and acceptance-support tests.
- Path packet: `.github/instructions/execution-core.instructions.md`.

## Browser capability lane
- `src/aios_tools/browser/` and `tests/test_browser_*.py`.
- `.github/workflows/browser-activation-replay.yml` and browser-core CI.
- Path packet: `.github/instructions/browser.instructions.md`.

## Benchmark lane
- `benchmarks/` and `src/aios_tools/benchmarks/`.
- benchmark CLI: `aios-bench`.
- `.github/workflows/benchmark-registry.yml`.
- Path packet: `.github/instructions/benchmark.instructions.md`.

## Audio/model dependency lane
- `src/aios_tools/audio_*.py`.
- `.github/workflows/audio-model-dependency-lock.yml`.
- `.github/workflows/demucs-model-quarantine.yml`.
- Path packet: `.github/instructions/audio-model.instructions.md`.

## Cartography/web lane
- `apps/cartography-web/` and `src/aios_tools/cartography/`.
- cartography-web CI lane and renderer CLI.
- Path packet: `.github/instructions/cartography-web.instructions.md`.

## Repository governance and contribution
- `.github/workflows/repo-governance.yml`.
- `.github/pull_request_template.md`.
- `CONTRIBUTING.md`, `SECURITY.md`, `docs/DEVELOPMENT.md`, `docs/VALIDATION.md`.

## Native agent roles
- `.github/agents/aios-tools-coordinator.agent.md`
- `.github/agents/aios-tools-implementer.agent.md`
- `.github/agents/aios-tools-reviewer.agent.md`
- `.github/agents/aios-tools-verifier.agent.md`
- `.github/agents/aios-tools-knowledge-steward.agent.md`

## Retrieval law
1. Start with handoff + authority + this index.
2. Load the smallest matching path-specific packet and domain evidence.
3. Load a skill only when the task matches its stable procedure.
4. Candidate lessons are memory, not enforceable law until explicitly promoted.
5. Use external Notion/Drive only when explicit escalation triggers apply.
6. Source does not imply authority; historical documents and receipts are evidence, not automatically current law.
7. Roles, skills, review output, and CI evidence do not grant acceptance, merge, release, deploy, capability, or global-governance authority.
