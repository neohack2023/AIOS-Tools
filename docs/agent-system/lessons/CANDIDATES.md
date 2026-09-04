# Candidate Lessons

## LESSON-AIOS-TOOLS-001 — Moving checkout is not immutable candidate binding

- candidate_state: `CONFIRMED_CANDIDATE`
- source_commit: `1550dcb6a5b39ed79f41bb6d124736b2b72c2871`
- source_paths_or_receipts: `docs/REPO_ADAPTATION_PROFILE.md`; current `.github/workflows/*.yml`; Drive `CI_EXACT_HEAD_BINDING_01 — drive_shadow v0.2`; Notion `VERIFIER_OWNED_ACCEPTANCE_01`
- observation: Phase 0 identified that existing CI used ordinary moving-ref checkout behavior rather than a mechanically proven exact-candidate binding contract. GitHub documents that `pull_request` workflows default to the synthetic merge ref unless checkout is explicitly bound to `github.event.pull_request.head.sha`. A green workflow is useful evidence, but the default checkout shape does not prove immutable candidate identity.
- affected_scope: repository CI / verifier evidence binding
- proposed_prevention_or_detection: acceptance-relevant pull-request workflows must derive `AIOS_CANDIDATE_SHA` from `github.event.pull_request.head.sha || github.sha`, check out that exact SHA, immediately compare `git rev-parse HEAD` against it, and mechanically audit the direct YAML `with.ref` relationship so nested/block-scalar text cannot impersonate the binding.
- promotion_state: `PROMOTED`
- promotion_target: `.github/workflows/*.yml`; `scripts/ci_exact_head_audit.py`; `scripts/agent_system_audit_phase5.py`; `docs/agent-system/audit/AUDIT_CONTRACT.md`
- promotion_evidence: owner-authorized 2026-09-04 adjudication after GitHub/Notion/Drive/current GitHub Docs cross-check; repair branch `aios/exact-head-ci-binding-01`; exact-head PR CI required before default-branch closure

The promoted invariant is obligation-scoped. It proves candidate identity for the workflow execution and its emitted evidence; it does not imply semantic completeness, merge authorization, release/deploy authority, or correctness outside the checks that actually ran.
