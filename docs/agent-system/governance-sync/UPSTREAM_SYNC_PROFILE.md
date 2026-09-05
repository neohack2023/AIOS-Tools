# AIOS-Tools Upstream Governance Sync Profile

State: `PHASE_5_COMPLETE / TARGET_SPECIFIC_SOURCE_SET / DELTA_ONLY / SELF_SUFFICIENT_REPO_ACTIVE`

## Purpose

Keep AIOS-Tools operationally self-sufficient for ordinary repository work while retaining a controlled route back to upstream AIOS governance when freshness, authority conflict, or owner direction requires it.

## Recurring upstream authority set

Only these stable governance sources participate in routine repository-governance synchronization:

| Source ID | Upstream role | Why it belongs |
| --- | --- | --- |
| `AIOS_TOOLS_EXECUTION_LAYER_CONTRACT` | AIOS-Tools architectural role and authority split | Defines Notion/Drive/GitHub responsibilities, execution shape, independence law, and default safety posture. |
| `AIOS_GITHUB_GOVERNED_EXECUTION_CONTRACT_v0.1` | Repository delivery governance | Defines bounded plans, branch/PR default, mechanical verification, governed handoff, and receipt expectations. |
| `VERIFIER_OWNED_ACCEPTANCE_01` | Verification/acceptance governance | Defines exact identity, obligation-scoped acceptance, model-advisory limits, and verifier precedence. |

Implementation plans, MASON receipts, research episodes, runtime feature contracts, and historical staging notes are evidence/history, not recurring upstream authority merely because they helped build this repository.

## Trigger contract

Use `.github/skills/sync-governance/SKILL.md` only for:
- stale/expiring local governance;
- suspected global/cross-repository governance drift;
- unresolved local authority conflict or material incompleteness;
- explicit owner-requested synchronization.

Ordinary repository work is external-fetch-free.

## Freshness contract

`sync_freshness_days = 30`.

A valid synchronization receipt may extend freshness only when its overall disposition is `NO_MATERIAL_DELTA` or `MATERIAL_DELTA_RECONCILED`.

`MATERIAL_DELTA_PENDING` never extends freshness. The repository may remain usable through the already-valid local window, but the unresolved delta must be separately adjudicated before renewal.

The receipt ledger is append-only. `GSYNC-AIOS-TOOLS-20260904-001` permanently records the first pending comparison. `GSYNC-AIOS-TOOLS-20260904-002` records the post-repair `MATERIAL_DELTA_RECONCILED` comparison and permitted freshness renewal.

## Verification responsibility split

For GitHub Actions repositories, generic platform semantics and security should be delegated to mature platform-aware validators before adding custom AIOS checks:

`actionlint -> generic Actions syntax/semantics`

`zizmor -> generic workflow security and supply-chain evidence`

`AIOS policy verifier -> exact-head identity + self-trigger observability + verifier execution context + evidence binding + target-specific authority invariants`

This is a target-specific implementation of a broader rule: use mature platform-native validators for generic platform behavior and keep AIOS custom verification focused on AIOS-owned trust obligations.

## Authority boundary

Synchronization is comparison and provenance, not authority transfer. It cannot itself:
- mutate runtime behavior;
- promote a lesson into law;
- change branch/release/deploy policy;
- widen capability/network/write authority;
- approve, merge, release, or deploy.

GitHub remains live implementation truth. Notion remains upstream architecture/governance authority. Drive remains evidence/control-plane projection where declared.

## Terminal Phase 5 state

`SELF_SUFFICIENT_REPO_ACTIVE / UPSTREAM_SYNC_ACTIVE / MATERIAL_DELTA_RECONCILED / FRESHNESS_RENEWED / NORMAL_REPO_WORK_EXTERNAL_FETCH_REQUIRED_FALSE / GOVERNANCE_VALID_THROUGH_2026-10-04`
