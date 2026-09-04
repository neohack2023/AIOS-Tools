# AIOS-Tools Upstream Governance Sync Profile

State: `PHASE_5_ACTIVE / TARGET_SPECIFIC_SOURCE_SET / DELTA_ONLY`

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

## Freshness contract

`sync_freshness_days = 30`.

A valid synchronization receipt may extend freshness only when its overall disposition is `NO_MATERIAL_DELTA` or `MATERIAL_DELTA_RECONCILED`.

`MATERIAL_DELTA_PENDING` never extends freshness. The repository may remain usable through the already-valid local window, but the unresolved delta must be separately adjudicated before renewal.

## Authority boundary

Synchronization is comparison and provenance, not authority transfer. It cannot itself:
- mutate runtime behavior;
- promote a lesson into law;
- change branch/release/deploy policy;
- widen capability/network/write authority;
- approve, merge, release, or deploy.

GitHub remains live implementation truth. Notion remains upstream architecture/governance authority. Drive remains evidence/control-plane projection where declared.
