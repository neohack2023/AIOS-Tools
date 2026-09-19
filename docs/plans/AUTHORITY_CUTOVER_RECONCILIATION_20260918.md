# Authority Cutover Reconciliation — 2026-09-18

## Objective

Reconcile AIOS-Tools' checked-in authority documentation with the current object-aware Drive cutover model without widening runtime, capability, merge, release, deployment, or memory authority.

## Base

- Repository: `neohack2023/AIOS-Tools`
- Base branch: `main`
- Base SHA: `fac2be2894aefe72320e2a2d01e16357c729fe96`
- Working branch: `agent/drive-authority-cutover-docs`
- Tracking issue: #62

## Governing external authority

`DRIVE_PRIMARY_AUTHORITY_OVERLAY — v0.3-object-aware — 2026-09-15`

- Drive ID: `1jjb-PrtcxCM7lQCepaEmy4SfyuC57MLuioOrPvnpCrA`
- Scope: `global-working-memory / AI_KNOWLEDGE_SYSTEM`
- Observed revision: `ANLCKQnDdOHGi3qL8a4Xf-CmMVFaortUdM0-vACK6y4sH_fZw0bpm0sExlpu5GIBMebxndpY5ym8s37aPA7QeKWljv3qNKnbK-UiER3v_38`

The overlay explicitly supersedes the blanket rule that Notion is always the first project-memory authority during migration.

## Authority model to project locally

1. GitHub remains authoritative for live repository implementation/execution facts.
2. Google Drive `AI_KNOWLEDGE_SYSTEM` is the primary durable external knowledge destination and authority for objects/scopes marked `DRIVE_VERIFIED` or `DRIVE_CURRENT`, and the default destination for new durable AIOS writes.
3. Notion is `LEGACY_SOURCE` fallback for exact objects missing or not parity-verified in Drive.
4. Research/source systems retain authority only for their source/research domain and do not self-promote.
5. Chat/LLM context remains transient evidence/routing context only.

Universal Notion retirement is not claimed.

## Scope

- `README.md`
- `SPEC.md`
- `docs/AUTHORITY_BOUNDARIES.md`
- `docs/DEVELOPMENT.md`
- `docs/agent-system/knowledge/KNOWLEDGE_INDEX.md`
- `docs/agent-system/context/REPOSITORY_HANDOFF.md`
- `docs/agent-system/governance-sync/UPSTREAM_SYNC_PROFILE.md`
- `docs/agent-system/context/governance-lock.yaml`
- one append-only governance-sync receipt for this authority delta

## Non-goals

- no runtime behavior change;
- no tool registry or execution-policy change;
- no branch-protection change;
- no capability/network/write widening;
- no deletion or rewriting of historical receipts;
- no declaration that all Notion content is migrated;
- no automatic merge.

## Validation

- Repository Governance on exact candidate head.
- AIOS-Tools CI on exact candidate head.
- Governance-sync receipt validator.
- Verify required authority markers describe the object-aware cutover consistently.
- Confirm `valid_through` is not renewed by the pending candidate receipt.

## Promotion rule

This branch is a repository projection of an already-authoritative upstream cutover. Human review controls merge. A post-merge governance resync remains required before freshness renewal.
