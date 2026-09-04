# AIOS-Tools Lesson Candidates

State: `PHASE_3_ACTIVE / HUMAN_PROMOTION_REQUIRED`

Candidate lessons preserve high-value review, incident, implementation, or verification findings without silently converting them into repository law.

## Required record fields

Each candidate must record:
- `id`
- `title`
- `candidate_state`
- `source_commit`
- `source_paths_or_receipts`
- `observation`
- `affected_scope`
- `proposed_prevention_or_detection`
- `promotion_state`
- `promotion_target` when promoted
- `promotion_evidence` when promoted

Allowed promotion states:
- `NONE`
- `PROPOSED`
- `PROMOTED`
- `REJECTED`
- `SUPERSEDED`

A candidate is not enforceable merely because it is well-supported.

## Promotion process

1. Human/governance adjudicates whether the lesson is general enough and valuable enough to preserve as law.
2. Choose the smallest target surface: common rule, department instruction, test/workflow, contract/policy, or documentation.
3. Make promotion as a separate governed repository change.
4. Record exact promotion evidence and target path here.
5. Phase 4 should later audit provenance and promotion consistency mechanically.
