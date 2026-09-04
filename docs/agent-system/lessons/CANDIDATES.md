# Candidate Lessons

## LESSON-AIOS-TOOLS-001 — Moving checkout is not immutable candidate binding

- candidate_state: `CONFIRMED_CANDIDATE`
- source_commit: `1550dcb6a5b39ed79f41bb6d124736b2b72c2871`
- source_paths_or_receipts: `docs/REPO_ADAPTATION_PROFILE.md`; current `.github/workflows/ci.yml`
- observation: Phase 0 identified that existing CI uses ordinary moving-ref checkout behavior rather than a mechanically proven exact-candidate binding contract. A green workflow is useful evidence, but the checkout shape alone does not prove immutable candidate identity.
- affected_scope: repository CI / verifier evidence binding
- proposed_prevention_or_detection: when an obligation requires exact candidate identity, explicitly bind checkout/evidence to the candidate SHA and test the semantic YAML structure rather than relying on nearby text or branch naming.
- promotion_state: `NONE`
- promotion_target: none
- promotion_evidence: none

This record is candidate institutional memory only. It does not modify CI or create a verifier requirement by itself. Phase 4 may later turn the accepted invariant into a mechanical audit obligation after separate adjudication.
