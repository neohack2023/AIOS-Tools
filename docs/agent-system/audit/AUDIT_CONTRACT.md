# AIOS-Tools Repository Organization Audit Contract

State: `PHASE_5_ACTIVE / DETERMINISTIC / FAIL_CLOSED_ON_ACCEPTED_ORGANIZATION_DRIFT / EXACT_HEAD_CI_BOUND`

This contract extends the existing Repository Governance workflow. It audits the repository-local operating package installed in Phases 1–5 without creating a second authority store.

## Audited obligations

1. Required agent-system routing surfaces exist and are non-empty.
2. The installed skill catalog is exactly the adaptive set: `plan-feature`, `review-pr`, `verify-head`, `harvest-lesson`, and `sync-governance`.
3. Every `SKILL.md` has matching `name`, non-empty `description`, and no `shell`/`bash` pre-approval.
4. Coordinator, Reviewer, Verifier, and Knowledge Steward profiles bind to their declared procedures, including Knowledge Steward -> `sync-governance`.
5. The five accepted Phase 2 department instruction packets exist and declare `applyTo` frontmatter.
6. `governance-lock.yaml` declares Phase 5, preserves local-first operation without upstream authority cutover, has not expired, and names the bounded synchronization role/source set/receipt.
7. Candidate lessons carry immutable full-SHA provenance and valid promotion state. A `PROMOTED` lesson must name its promotion target and promotion evidence.
8. The semantic handoff declares Phase 5 governance synchronization active.
9. Public repository agent surfaces do not contain private Notion or Google Drive workspace URLs.
10. The governance workflow binds its own checkout and receipt to the exact candidate SHA it claims to inspect.
11. Every acceptance-relevant `pull_request` workflow in the declared audit set must use a full-SHA-pinned `actions/checkout` step whose direct `with.ref` equals `${{ github.event.pull_request.head.sha || github.sha }}`, disable persisted checkout credentials, and immediately verify `git rev-parse HEAD` against that same immutable GitHub event context with a constrained failure-enforcing command shape.
12. Exact-head binding checks must inspect constrained workflow structure and fail closed on unsupported trigger spellings, nested/block-scalar impersonation, suppressed comparisons, or any `AIOS_CANDIDATE_SHA` environment indirection that could be shadowed at a narrower scope.

## Exact-head evidence scope

`LESSON-AIOS-TOOLS-001` is promoted by owner adjudication after cross-checking the live AIOS-Tools workflows, `VERIFIER_OWNED_ACCEPTANCE_01`, Drive `CI_EXACT_HEAD_BINDING_01`, and current GitHub `pull_request` event semantics.

The resulting invariant proves only that a workflow and its emitted evidence ran against the exact candidate it claims. It does not prove that every relevant behavior was tested, upgrade advisory/model review into terminal authority, or authorize merge, release, deployment, capability widening, or global-governance mutation.

## Governance synchronization

Phase 5 bounded upstream synchronization remains Knowledge-Steward-owned and receipt-bound. Fetch success alone never renews governance freshness. A material pending upstream delta leaves `valid_through` unchanged until the corresponding repository/governance repair is promoted and verified.

## Receipt

- `scripts/agent_system_audit_phase5.py` emits `outputs/agent-system-audit.json` with schema `AIOS_TOOLS_ORGANIZATION_AUDIT_PHASE5_01`.
- `scripts/ci_exact_head_audit.py` emits `outputs/ci-exact-head-audit.json` with schema `AIOS_TOOLS_CI_EXACT_HEAD_AUDIT_02`.
- `scripts/governance_sync.py` validates the latest bounded governance synchronization receipt.
- `.github/workflows/repo-governance.yml` owns execution and uploads these receipts as exact-candidate workflow evidence.

## Failure semantics

A failure blocks the corresponding Repository Governance obligation for that candidate. It does not itself revoke unrelated authority, merge a change, release software, refresh governance freshness, or modify upstream governance.
