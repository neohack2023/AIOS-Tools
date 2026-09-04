# AIOS-Tools Repository Organization Audit Contract

State: `PHASE_5_ACTIVE / DETERMINISTIC / FAIL_CLOSED_ON_ACCEPTED_ORGANIZATION_DRIFT / GOVERNANCE_SYNC_VALIDATED_SEPARATELY`

This contract extends the existing Repository Governance workflow. It audits the repository-local operating package installed in Phases 1–5 without creating a second authority store.

## Audited obligations

1. Required agent-system routing surfaces exist and are non-empty.
2. The installed skill catalog is exactly the adaptive set: `plan-feature`, `review-pr`, `verify-head`, `harvest-lesson`, and `sync-governance`.
3. Every `SKILL.md` has matching `name`, non-empty `description`, and no `shell`/`bash` pre-approval.
4. Coordinator, Reviewer, Verifier, and Knowledge Steward profiles bind to their declared procedures; Phase 5 additionally binds Knowledge Steward to `sync-governance`.
5. The five accepted Phase 2 department instruction packets exist and declare `applyTo` frontmatter.
6. `governance-lock.yaml` declares Phase 5, preserves local-first operation without upstream authority cutover, identifies the Knowledge Steward as sync owner, and has not expired.
7. Candidate lessons carry immutable full-SHA provenance and valid promotion state. A `PROMOTED` lesson must name its promotion target and promotion evidence.
8. The semantic handoff declares Phase 5 governance synchronization active.
9. Public repository agent surfaces do not contain private Notion or Google Drive workspace URLs.
10. The audit workflow binds its own checkout and receipt to the exact candidate SHA it claims to inspect.
11. Phase 5 sync routing/profile/receipt surfaces exist. Their digest/source/freshness semantics are validated by the separate governance-sync validator rather than duplicated inside the organization auditor.

## Non-obligations

The audit does **not** automatically promote lesson candidates into law. `LESSON-AIOS-TOOLS-001` remains unpromoted; the broader repository CI exact-head binding issue is now a `MATERIAL_DELTA_PENDING` governance-sync finding, not a silently created audit rule.

The audit does not install `prepare-release`, widen branch protection, authorize release/deploy, repair pending governance deltas, or move global AIOS governance into GitHub.

## Receipt

`scripts/agent_system_audit.py` remains the Phase 4 audit foundation. `scripts/agent_system_audit_phase5.py` composes it with Phase 5 skill/lock/handoff expectations and emits `outputs/agent-system-audit.json` with exact candidate identity, UTC generation time, PASS/FAIL state, and stable failure codes.

`scripts/governance_sync.py` separately emits `outputs/governance-sync-validation.json` proving the synchronization receipt's SHA-256 binding, source-set identity, delta disposition, freshness behavior, and authority boundary.

The existing `.github/workflows/repo-governance.yml` owns both checks and uploads both receipts as workflow evidence.

## Failure semantics

A failure blocks the corresponding Repository Governance obligation for that candidate. It does not by itself revoke unrelated authority, merge a change, release software, modify upstream governance, or authorize repair.
