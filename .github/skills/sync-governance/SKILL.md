---
name: sync-governance
description: Compare AIOS-Tools' checked-in repository governance against the pinned upstream AIOS authority set, record only the delta, and emit a provenance-bound synchronization receipt. Use only for explicit governance refresh, stale-bundle review, authority conflict, or owner-requested upstream synchronization.
---

# Sync Governance

This procedure is owned by the Knowledge Steward. It does not grant architecture, merge, release, deploy, capability, or mutation authority.

## Trigger
Run only when one of these conditions is true:
1. `governance-lock.yaml` is stale or approaching `valid_through`;
2. a cross-repository/global AIOS governance change may affect AIOS-Tools;
3. checked-in authority sources conflict or are materially incomplete;
4. the owner explicitly requests upstream synchronization.

Ordinary repository work remains local-first and must not fetch Notion/Drive just to reconstruct context.

## Pinned upstream source set
Load only the source IDs declared by `docs/agent-system/governance-sync/UPSTREAM_SYNC_PROFILE.md` and `governance-lock.yaml`. Do not broaden the source set merely because related implementation plans, receipts, or research are nearby.

For every source record:
- stable source ID;
- opaque upstream page/object ID;
- observed `last_edited_at` or equivalent source version;
- authority classification.

## Compare delta only
Compare upstream law to the current checked-in repository governance bundle. Classify each material difference as:
- `RECONCILED` — local state already preserves the upstream law or a separately authorized bounded exception is explicitly recorded;
- `PENDING` — material upstream law is not yet reconciled locally and requires a separately governed change;
- `NON_MATERIAL` — wording/history difference with no governing effect.

Do not copy full upstream pages into the repository and do not convert implementation history into recurring authority.

## Freshness law
Overall disposition is one of:
- `NO_MATERIAL_DELTA`;
- `MATERIAL_DELTA_RECONCILED`;
- `MATERIAL_DELTA_PENDING`.

Only the first two may renew `valid_through`, and only when the receipt and governance lock agree mechanically. `MATERIAL_DELTA_PENDING` must leave freshness unchanged or expiring.

A successful fetch is not a successful synchronization.

## Receipt
Write an immutable JSON receipt under `docs/agent-system/governance-sync/receipts/` containing repository identity, source identities/versions, delta disposition, explicit deltas, freshness decision, and authority boundary. Bind the receipt SHA-256 from `governance-lock.yaml`.

## Stop conditions
Stop and report `MATERIAL_DELTA_PENDING` rather than silently repairing when:
- a material upstream law would require changing runtime behavior, CI acceptance semantics, authority, branch/release policy, or another promoted rule;
- source identity/version is ambiguous;
- the pinned authority set conflicts internally;
- the requested change would widen capability or authority.
