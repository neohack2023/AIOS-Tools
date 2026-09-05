# AIOS-Tools Knowledge Index

State: `PHASE_5_ACTIVE / PHASE_5_COMPLETE / SELF_SUFFICIENT_REPO_ACTIVE`

Use this index to route questions to the smallest authoritative repository surface.

## Repository identity and operating law
- `README.md` — product/repository identity and user-facing operation.
- `SPEC.md` — implementation scope and constraints.
- `AGENTS.md` — repository agent instructions.
- `.github/copilot-instructions.md` — thin Copilot adapter into canonical local context.
- `docs/AUTHORITY_BOUNDARIES.md` — GitHub vs upstream Notion/Drive authority.
- `docs/REPO_ADAPTATION_PROFILE.md` — Phase 0 repository-specific rollout decisions.
- `docs/agent-system/context/governance-lock.yaml` — local governance freshness, Phase 5 state, source-set binding, and last sync receipt digest.
- `docs/agent-system/adapters/AGENT_ADAPTER_MAP.md` — role and department routing.
- `docs/agent-system/ROLE_AND_SKILL_PROFILE.md` — adaptive role/skill binding.

## Repository-native procedures
- `.github/skills/plan-feature/SKILL.md`
- `.github/skills/review-pr/SKILL.md`
- `.github/skills/verify-head/SKILL.md`
- `.github/skills/harvest-lesson/SKILL.md`
- `.github/skills/sync-governance/SKILL.md`
- Review router: `docs/agent-system/review/REVIEW_RULES.md`.
- Institutional-memory lane: `docs/agent-system/lessons/README.md` and `docs/agent-system/lessons/CANDIDATES.md`.

## Organization and CI verification
- Audit contract: `docs/agent-system/audit/AUDIT_CONTRACT.md`.
- Organization auditor foundation: `scripts/agent_system_audit.py`.
- Phase 5 audit composition: `scripts/agent_system_audit_phase5.py`.
- AIOS-specific exact-head policy: `scripts/ci_exact_head_audit.py`.
- Generic GitHub Actions syntax/semantics: actionlint in `.github/workflows/repo-governance.yml`.
- Generic GitHub Actions security/supply-chain evidence: blocking zizmor in `.github/workflows/repo-governance.yml`.
- Auditor tests: `tests/test_agent_system_audit.py` and `tests/test_ci_exact_head_audit.py`.
- Owning workflow: `.github/workflows/repo-governance.yml`.

AIOS custom policy does not reimplement the whole GitHub Actions language. Mature platform-aware validators own generic platform behavior; AIOS owns target-specific trust bindings.

## Governance synchronization
- Target-specific source set: `docs/agent-system/governance-sync/UPSTREAM_SYNC_PROFILE.md`.
- Sync router: `docs/agent-system/governance-sync/README.md`.
- Historical pending receipt: `docs/agent-system/governance-sync/receipts/GSYNC-AIOS-TOOLS-20260904-001.json`.
- Terminal reconciliation receipt: `docs/agent-system/governance-sync/receipts/GSYNC-AIOS-TOOLS-20260904-002.json`.
- Validator: `scripts/governance_sync.py`.
- Validator tests: `tests/test_governance_sync.py`.
- Validation output: `outputs/governance-sync-validation.json` in workflow evidence.

Current disposition: `MATERIAL_DELTA_RECONCILED`. Freshness renewal is applied and `valid_through` is `2026-10-04`. Ordinary repository work remains external-fetch-free.

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

## Retrieval law
1. Start with handoff + governance lock + authority + this index.
2. Load the smallest matching path-specific packet and domain evidence.
3. Load a skill only when the task matches its stable procedure.
4. Candidate lessons are memory, not enforceable law until explicitly promoted.
5. Use external Notion/Drive only when explicit escalation/freshness triggers apply; when syncing, use only the pinned source set.
6. Source does not imply authority; historical documents and receipts are evidence, not automatically current law.
7. A successful fetch is not a successful sync, and a successful sync is not mutation authority.
8. Roles, skills, review output, audit output, sync output, and CI evidence do not grant acceptance, merge, release, deploy, capability, mutation, or global-governance authority.
