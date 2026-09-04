# AIOS-Tools Knowledge Index

State: `PHASE_1_CANDIDATE`

Use this index to route questions to the smallest authoritative repository surface.

## Repository identity and operating law
- `README.md` — product/repository identity and user-facing operation.
- `SPEC.md` — implementation scope and constraints.
- `AGENTS.md` — repository agent instructions.
- `docs/AUTHORITY_BOUNDARIES.md` — GitHub vs upstream Notion/Drive authority.
- `docs/REPO_ADAPTATION_PROFILE.md` — Phase 0 repository-specific rollout decisions.

## Shared capability and execution core
- `src/aios_tools/` — live Python implementation.
- `contracts/` — machine-facing contracts and schemas.
- `policies/` — execution/policy constraints.
- `fixtures/` — deterministic fixtures and bounded test evidence inputs.
- `tests/` — executable regression and acceptance-support tests.

## Interfaces and adapters
- CLI entry point: `aios-tools`.
- MCP entry point: `aios-tools-mcp`.
- future adapter/connector surfaces: inspect `src/`, `extensions/`, and the governing contract before changes.

## Browser capability lane
- browser implementation/tests under `src/aios_tools/` and `tests/test_browser_*.py`.
- `.github/workflows/browser-activation-replay.yml`.
- browser-core job in `.github/workflows/ci.yml`.
- use `docs/VALIDATION.md` plus the affected policy/contract/fixture set.

## Benchmark lane
- `benchmarks/`.
- benchmark CLI: `aios-bench`.
- `.github/workflows/benchmark-registry.yml`.
- `docs/BENCHMARK_ENVIRONMENT.md` when benchmark environment identity matters.

## Audio/model dependency lane
- `.github/workflows/audio-model-dependency-lock.yml`.
- `.github/workflows/demucs-model-quarantine.yml`.
- inspect corresponding contracts, policies, fixtures, profiles, and tests before altering model/dependency behavior.

## Cartography/web lane
- `apps/cartography-web/`.
- cartography renderer CLI: `aios-cartography-render`.
- cartography-web job in `.github/workflows/ci.yml`.
- relevant `docs/cartography-slice-*.md` documents describe bounded historical slices; treat GitHub code/tests as live implementation truth.

## Repository governance and contribution
- `.github/workflows/repo-governance.yml`.
- `.github/pull_request_template.md`.
- `CONTRIBUTING.md`.
- `SECURITY.md`.
- `docs/DEVELOPMENT.md`.
- `docs/VALIDATION.md`.

## Semantic resume
- `docs/agent-system/context/REPOSITORY_HANDOFF.md` — current semantic operating state.
- resolve mutable head/branch/PR/CI facts live from GitHub instead of copying them forward as timeless context.

## Retrieval law

1. Start with handoff + authority + this index.
2. Read only the domain-specific implementation, contract, policy, fixture, tests, and workflow required by the task.
3. Use external Notion/Drive only when the handoff's explicit escalation triggers apply.
4. Source does not imply authority; a historical document or receipt is evidence, not automatically current law.
