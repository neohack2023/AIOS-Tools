# REPO_ADAPTATION_PROFILE — AIOS-Tools

State: `PHASE_0_COMPLETE / INVENTORY_FROZEN / NO_PHASE_1_ACTIVATION`

## Frozen repository identity

- Repository: `neohack2023/AIOS-Tools`
- Visibility: public
- Default branch: `main`
- Frozen Phase 0 head: `a8b47f74f0d2f7e6bcfaf25399ebc5ce7dd48e20`
- Frozen tree: `619beda8dc762996274e8a58aabd694a177291b3`
- Head message: `Activate execution trust binding canary (#57)`
- Phase 0 authorization: owner-approved inventory + adaptation-profile write only
- Phase 1 authorization: `NO`

Current mutable repository identity must always be resolved live from GitHub. The SHA above is the immutable input snapshot used to generate this profile, not a permanent claim about current `main`.

## Repository purpose and implementation shape

`AIOS-Tools` is already an independent governed capability and execution layer for AIOS rather than a blank application repository. It contains a Python shared core, CLI and MCP adapter surfaces, browser-capability code/tests, benchmark infrastructure, cartography/web application work, contracts, policies, fixtures, registries, profiles, extensions, and multiple domain-specific CI workflows.

Primary package/runtime facts observed in Phase 0:

- Python package: `aios-tools` v0.1.0
- Python requirement: `>=3.11`
- CI runtime: Python 3.12
- Primary dependencies: `jsonschema`, `mcp`
- Optional browser stack: Playwright + keyring
- Main console surfaces: `aios-tools`, `aios-tools-mcp`, `aios-cartography-render`, `aios-bench`
- Web subproject: `apps/cartography-web` with Node 22 CI

## Existing repository operating surfaces

### Reuse as canonical inputs

The following already exist and SHOULD be reused rather than replaced by the self-sufficiency template:

- `AGENTS.md`
  - already defines read order, repository authority, change rules, required validation, and PR evidence
  - explicitly states that repository authority covers live implementation/tool-version facts, while architecture/memory/governance remain upstream-governed
  - already requires one concern per branch/PR and forbids ordinary direct `main` commits
- `README.md`
- `SPEC.md`
- `CONTRIBUTING.md`
- `SECURITY.md`
- `docs/ARCHITECTURE.md`
- `docs/AUTHORITY_BOUNDARIES.md`
- `docs/DEVELOPMENT.md`
- `docs/VALIDATION.md`
- `.github/pull_request_template.md`
- `.github/workflows/repo-governance.yml`

Phase 1 should link and compact these surfaces into a repository-local context router, not fork their semantics into duplicate documents.

## Existing mechanical verification

### Core CI

`.github/workflows/ci.yml` already runs on pull requests and pushes to `main` and contains distinct lanes for:

1. Linux shared-core + CLI + MCP smoke
2. Windows shared-core + CLI + MCP smoke
3. browser-core Playwright/local-server fixtures
4. cartography-web unit/build/E2E evidence

Observed strengths:

- Linux + Windows coverage for the Python core
- browser-specific validation is already separated
- cartography web has build and interaction/screenshot regression evidence
- browser evidence is uploaded as an artifact
- required command surfaces are exercised, not merely imported

Observed Phase 0 adaptation notes:

- checkout currently uses moving `actions/checkout@v4`, not an exact candidate-head binding contract
- no repository-self-sufficiency audit exists yet
- no governance-lock freshness or sync-receipt validation exists yet
- these are Phase 4/5 candidates, not Phase 0 mutations

### Repository governance CI

`.github/workflows/repo-governance.yml` already checks:

- required repository documentation surfaces exist and are non-empty
- authority-boundary markers mention Notion, Google Drive, and live source-code authority
- README carries the `authority_transfer` marker
- Python sources/tests compile

This workflow SHOULD be extended/adapted in later phases rather than replaced by the AI Knowledge System auditor wholesale.

## Domain-specific workflow departments

The workflow inventory includes at least:

- `ci.yml`
- `repo-governance.yml`
- `browser-activation-replay.yml`
- `benchmark-registry.yml`
- `audio-model-dependency-lock.yml`
- `demucs-model-quarantine.yml`

These are evidence that AIOS-Tools already has distinct operational departments. The adaptive rollout SHOULD preserve these as domain-local verification/guardrail lanes.

Candidate future path-specific departments include:

- shared execution core / registry / policy
- browser capability
- benchmark registry
- audio/model dependency governance
- cartography/web application
- MCP/CLI adapters

Do not manufacture a department merely to mirror the reference repository. Create path-specific agent/instruction routing only where the existing code/workflow structure demonstrates a real boundary.

## Authority profile

### Repository-local authority

GitHub / this repository is authoritative for:

- source code
- executable contracts/tests
- tool registry/policy implementation
- current branches/commits/PRs/CI
- package/tool versions
- repository-local implementation documentation

### Upstream authority remains external

The existing repository instructions explicitly retain upstream authority for AIOS architecture, memory doctrine, and governance. Phase 1–5 self-sufficiency MUST therefore vendor only the public-safe subset needed for normal repository execution. It must not silently convert repository-local context into global AIOS authority.

### Direct-main rule

The current repository-local default is explicit: `Do not commit directly to main.`

Any future direct-main staging requires a new, bounded owner exception. The Phase 0 profile write is the only mutation authorized by this episode and must not be interpreted as reusable authority for Phase 1–5.

## Adaptation matrix

| Template component | Decision | AIOS-Tools adaptation |
| --- | --- | --- |
| compact root instruction router | `REUSE + ADAPT` | preserve existing `AGENTS.md`; later add only missing local-self-sufficiency routing |
| project charter | `REUSE` | derive from README + SPEC; avoid duplicate mission prose unless a compact context file proves useful |
| authority map | `REUSE + ADAPT` | `docs/AUTHORITY_BOUNDARIES.md` is already canonical repository-local input |
| architecture map | `REUSE` | `docs/ARCHITECTURE.md` already exists |
| development/validation guidance | `REUSE` | existing DEVELOPMENT + VALIDATION docs |
| semantic handoff | `ADD` | no compact repository-local hot-resume handoff observed in Phase 0 |
| knowledge index/router | `ADD` | needed to route existing docs/contracts/policies/fixtures without external retrieval |
| governance bundle/lock | `ADD, THIN` | vendor only execution-relevant global law; preserve existing authority docs |
| generic agent company roles | `ADAPT` | install only roles useful for this repo; do not assume all reference roles are necessary |
| path-specific instructions | `ADD SELECTIVELY` | browser, benchmark, audio/model, cartography, adapters only where inspection proves stable boundaries |
| lifecycle skills | `ADAPT` | start from repeated workflows; likely plan-feature, review-pr, verify-head, harvest-lesson, prepare-release; sync-governance only after Phase 5 source-set design |
| anti-pattern candidate lane | `ADD` | seed from AIOS-Tools' own incidents/reviews, not PR #67–#70 from another repo unless the generalized lesson is explicitly imported |
| feature dossiers | `ADAPT` | use only for material governed capability slices; existing slice docs/plans may already satisfy much of this need |
| organization audit | `EXTEND EXISTING` | build on `repo-governance.yml`; avoid parallel duplicate auditor where one workflow can own the obligation cleanly |
| upstream sync | `ADD IN PHASE 5` | Knowledge Steward-only, delta-only, receipt-bound, fail-closed freshness renewal |
| direct-main staging | `OMIT AS DEFAULT` | existing AGENTS law requires branch/PR delivery unless owner grants a new bounded exception |

## Proposed Phase 1 shape

If separately authorized, Phase 1 SHOULD be a consolidation layer rather than a scaffold dump.

Minimum candidate additions:

1. `docs/agent-system/context/REPOSITORY_HANDOFF.md`
2. `docs/agent-system/knowledge/KNOWLEDGE_INDEX.md`
3. a thin repository governance bundle/lock pointing to existing authority/architecture/development/validation docs
4. a compact index of domain departments and their existing workflows
5. minimal routing additions to existing `AGENTS.md` only where required

Likely Phase 1 reuse targets:

- README + SPEC = mission/product charter
- AUTHORITY_BOUNDARIES = authority map
- ARCHITECTURE = system map
- DEVELOPMENT = implementation conventions
- VALIDATION = verification doctrine
- repo-governance workflow = future self-audit substrate

## Proposed later-phase specialization

### Phase 2

Prefer a small native-agent set. Candidate initial roles:

- Coordinator
- Implementer
- Reviewer
- Verifier
- Knowledge Steward

Planner and Release Steward should be added only if repeated AIOS-Tools work demonstrates a distinct enough workflow to justify them.

Path instructions should be derived from actual code ownership/risk boundaries, especially browser, registry/policy, benchmark, audio/model, and cartography/web surfaces.

### Phase 3

Promote only repeated procedures into skills. The reference skill catalog is a candidate library, not a mandatory set.

### Phase 4

Extend repository governance mechanically to include whatever Phase 1–3 introduce. Prefer one coherent repository-organization verifier over parallel overlapping governance workflows.

### Phase 5

Pin only stable global/cross-repository governance sources. Never make mutable AIOS-Tools implementation plans part of the recurring upstream source set.

## Risks / constraints discovered in Phase 0

1. AIOS-Tools already has mature authority language. Copying the reference repository's governance prose could create conflicting law.
2. Multiple specialized CI workflows mean a generic single-lane audit would lose useful domain boundaries.
3. Existing AGENTS instructions forbid direct `main` changes by default; later phases must honor that unless explicitly overridden by the owner.
4. The repository is public. No private Notion/Drive URLs, personal memory, credentials, provider bindings, or private evidence may be vendored.
5. Current GitHub branch protection is not enabled on `main`; governance currently lives primarily in repository instructions/workflows rather than branch protection.
6. Existing CI uses moving action major tags. Immutable action pinning/exact-candidate binding may be worth a separate verification-hardening concern, but it is outside Phase 0.

## Phase 0 acceptance

Phase 0 is complete when:

- exact input head is frozen;
- existing repository operating surfaces are inventoried;
- reuse/adapt/add/omit/defer decisions are recorded;
- no Phase 1 behavior, agent, skill, CI, authority, capability, release, or deployment mutation occurs.

Current result:

`PHASE_0_COMPLETE / ADAPTATION_PROFILE_WRITTEN / PHASE_1_NOT_AUTHORIZED`
