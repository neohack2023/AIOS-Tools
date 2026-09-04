# Governance synchronization

Phase 5 turns external governance access into a bounded maintenance shipment rather than normal repository bootstrap.

Canonical procedure: `.github/skills/sync-governance/SKILL.md`.

Target-specific authority set: `UPSTREAM_SYNC_PROFILE.md`.

Immutable synchronization receipts: `receipts/*.json`.

Mechanical validator: `scripts/governance_sync.py`.

## Law

`local repository context -> explicit sync trigger -> Knowledge Steward -> pinned upstream sources -> delta only -> receipt -> mechanical validation -> optional freshness renewal`

A fetch does not grant authority. A synchronization receipt does not grant authority. `MATERIAL_DELTA_PENDING` cannot refresh governance freshness.

The repository must never store private Notion/Drive workspace URLs in this public governance surface; receipts bind opaque upstream IDs and observed source versions instead.
