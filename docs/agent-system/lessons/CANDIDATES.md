# Candidate Lessons

## LESSON-AIOS-TOOLS-001 — Moving checkout is not immutable candidate binding

- candidate_state: `CONFIRMED_CANDIDATE`
- source_commit: `1550dcb6a5b39ed79f41bb6d124736b2b72c2871`
- source_paths_or_receipts: `docs/REPO_ADAPTATION_PROFILE.md`; current `.github/workflows/*.yml`; Drive `CI_EXACT_HEAD_BINDING_01 — drive_shadow v0.2`; Notion `VERIFIER_OWNED_ACCEPTANCE_01`; PR #59 review history
- observation: Phase 0 identified that existing CI used ordinary moving-ref checkout behavior rather than a mechanically proven exact-candidate binding contract. GitHub documents that `pull_request` workflows default to a synthetic merge ref unless checkout is explicitly bound to `github.event.pull_request.head.sha`. PR #59 then demonstrated that a verifier which reimplements broad GitHub Actions semantics with source-text heuristics creates its own bypass surface.
- affected_scope: repository CI / verifier evidence binding
- proposed_prevention_or_detection: acceptance-relevant pull-request workflows bind checkout directly to `${{ github.event.pull_request.head.sha || github.sha }}`, disable persisted credentials, and immediately verify `git rev-parse HEAD` in a constrained runner context. actionlint owns generic Actions syntax/semantics; zizmor supplies generic security evidence; the AIOS policy verifier owns only exact-head identity, self-trigger observability, and verifier execution-context restrictions.
- promotion_state: `PROMOTED`
- promotion_target: `.github/workflows/*.yml`; `scripts/ci_exact_head_audit.py`; `scripts/agent_system_audit_phase5.py`; `docs/agent-system/audit/AUDIT_CONTRACT.md`; `docs/plans/AIOS_TOOLS_ACTIONS_VERIFIER_ARCHITECTURE_01.md`
- promotion_evidence: owner-authorized 2026-09-04 adjudication after GitHub/Notion/Drive/current GitHub Docs cross-check; PR #59 repair evidence; admin-authorized direct-main architectural repair after review-convergence breaker

The promoted invariant is obligation-scoped. It proves candidate identity for the workflow execution and its emitted evidence; it does not imply semantic completeness, merge authorization, release/deploy authority, or correctness outside the checks that actually ran.
