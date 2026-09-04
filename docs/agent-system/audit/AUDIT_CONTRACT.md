# AIOS-Tools Repository Organization Audit Contract

State: `PHASE_4_ACTIVE / DETERMINISTIC / FAIL_CLOSED_ON_ACCEPTED_ORGANIZATION_DRIFT`

This contract extends the existing Repository Governance workflow. It audits the repository-local operating package installed in Phases 1–3 without creating a second authority store.

## Audited obligations

1. Required agent-system routing surfaces exist and are non-empty.
2. The installed skill catalog is exactly the Phase 3 adaptive set: `plan-feature`, `review-pr`, `verify-head`, and `harvest-lesson`.
3. Every `SKILL.md` has matching `name`, non-empty `description`, and no `shell`/`bash` pre-approval.
4. Coordinator, Reviewer, Verifier, and Knowledge Steward profiles bind to their declared procedures.
5. The five accepted Phase 2 department instruction packets exist and declare `applyTo` frontmatter.
6. `governance-lock.yaml` declares Phase 4, preserves local-first operation without upstream authority cutover, and has not expired.
7. Candidate lessons carry immutable full-SHA provenance and valid promotion state. A `PROMOTED` lesson must name its promotion target and promotion evidence.
8. The semantic handoff declares Phase 4 organization audit active.
9. Public repository agent surfaces do not contain private Notion or Google Drive workspace URLs.
10. The audit workflow binds its own checkout and receipt to the exact candidate SHA it claims to inspect.

## Non-obligations

Phase 4 does **not** automatically promote lesson candidates into law. In particular, `LESSON-AIOS-TOOLS-001` remains unpromoted, so the broader repository CI exact-head binding issue remains a candidate governance concern rather than a blocking Phase 4 invariant.

Phase 4 also does not install `prepare-release` or `sync-governance`, widen branch protection, authorize release/deploy, or move global AIOS governance into GitHub.

## Receipt

`scripts/agent_system_audit.py` emits `outputs/agent-system-audit.json` with schema `AIOS_TOOLS_ORGANIZATION_AUDIT_01`, exact candidate identity, UTC generation time, PASS/FAIL state, and stable failure codes.

The existing `.github/workflows/repo-governance.yml` owns execution of the auditor and uploads the receipt as workflow evidence.

## Failure semantics

A failure blocks the Repository Governance obligation for that candidate. It does not by itself revoke unrelated authority, merge a change, release software, or modify upstream governance.
