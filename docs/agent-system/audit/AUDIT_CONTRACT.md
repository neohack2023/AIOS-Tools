# AIOS-Tools Repository Organization Audit Contract

State: `PHASE_5_ACTIVE / DETERMINISTIC / ACTIONS_NATIVE_VALIDATION / EXACT_HEAD_CI_BOUND`

This contract extends the existing Repository Governance workflow. It audits the repository-local operating package installed in Phases 1–5 without creating a second authority store.

## Validation architecture

GitHub Actions validation is deliberately split by obligation.

1. **actionlint 1.7.12** owns generic GitHub Actions workflow syntax, expression, action-input, reusable-workflow, and supported script static checks.
2. **zizmor 1.29.0** supplies independent generic GitHub Actions security evidence. It is advisory in this repository until its existing finding baseline is explicitly adjudicated; it does not own AIOS merge authority.
3. **`scripts/ci_exact_head_audit.py`** owns only AIOS trust-binding policy:
   - exact PR-head checkout identity;
   - fail-closed checkout identity verification;
   - self-trigger observability for audited workflow edits;
   - a constrained verifier execution context;
   - exact-candidate evidence naming/binding where declared.
4. Repository Governance composes those obligations. Passing one layer does not imply another layer passed.

This separation is intentional. AIOS owns its policy, not a parallel implementation of the full GitHub Actions language.

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
10. Repository Governance binds its own checkout and receipts to the exact candidate SHA it claims to inspect.
11. Every acceptance-relevant `pull_request` workflow in the declared audit set:
    - uses a full-SHA-pinned `actions/checkout`;
    - binds `with.ref` directly to `${{ github.event.pull_request.head.sha || github.sha }}`;
    - disables persisted credentials;
    - begins each job with checkout followed immediately by a closed identity-verification step;
    - does not make checkout or identity verification conditional/non-fatal;
    - does not run the acceptance job inside a container;
    - does not override identity-sensitive shell/Git environment variables at workflow/job scope.
12. A path-filtered audited workflow must include its own workflow path exactly. `paths-ignore` and negative `paths` patterns are forbidden for audited acceptance workflows so workflow-definition edits cannot evade current-head execution.
13. Workflow syntax variants are not policy failures merely because their source spelling differs. actionlint owns generic syntax; the AIOS policy layer consumes parsed YAML semantics and rejects only unsupported AIOS trust-binding structures.

## Exact-head evidence scope

`LESSON-AIOS-TOOLS-001` is promoted by owner adjudication after cross-checking live AIOS-Tools workflows, `VERIFIER_OWNED_ACCEPTANCE_01`, Drive `CI_EXACT_HEAD_BINDING_01`, current GitHub `pull_request` semantics, and repeated PR #59 review evidence.

The resulting invariant proves only that a workflow and its emitted evidence ran against the exact candidate it claims. It does not prove every relevant behavior was tested, upgrade model review into terminal authority, or authorize merge, release, deployment, capability widening, or global-governance mutation.

## External tool pins

- actionlint release: `v1.7.12`, tag commit `914e7df21a07ef503a81201c76d2b11c789d3fca`.
- actionlint Linux amd64 release asset SHA-256: `8aca8db96f1b94770f1b0d72b6dddcb1ebb8123cb3712530b08cc387b349a3d8`.
- zizmor action: `zizmorcore/zizmor-action@3dc1ecc9bcb9e94e9b2c709687979e1298497054` (`v0.6.2`).
- zizmor engine: `1.29.0`, whose container digest is resolved by the pinned action's version manifest.

Changing these pins is a governance/dependency update and must be independently reviewed.

## Governance synchronization

Phase 5 bounded upstream synchronization remains Knowledge-Steward-owned and receipt-bound. Fetch success alone never renews governance freshness. A material pending upstream delta leaves `valid_through` unchanged until the corresponding repository/governance repair is promoted and verified.

## Receipts

- `scripts/agent_system_audit_phase5.py` emits `outputs/agent-system-audit.json`.
- `scripts/ci_exact_head_audit.py` emits `outputs/ci-exact-head-audit.json` with schema `AIOS_TOOLS_CI_EXACT_HEAD_POLICY_04`.
- `scripts/governance_sync.py` validates the latest bounded governance synchronization receipt.
- Repository Governance uploads deterministic AIOS receipts. actionlint is a blocking generic syntax gate; zizmor is currently advisory generic security evidence.

## Failure semantics

A deterministic AIOS or actionlint failure blocks the corresponding Repository Governance obligation for that candidate. A zizmor finding is advisory until separately promoted into a blocking baseline. None of these checks can merge a change, release software, refresh governance freshness, or modify upstream governance.
