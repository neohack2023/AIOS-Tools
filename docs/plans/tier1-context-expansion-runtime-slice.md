# Tier 1 Context Expansion Runtime Slice

## Status

Candidate implementation on `agent/tier1-context-expansion-runtime`.

Scope: `global-working-memory`

Mode: `READ_ONLY`

Authority transfer: forbidden.

## Existing authority and implementation state

This slice does not define a new AIOS retrieval architecture.

The governing Notion and Drive contracts already define:

- `Context Expansion Decision Record/0.1`
- L0, L1, and L2 context tiers
- sufficiency states `SUFFICIENT`, `INSUFFICIENT`, `UNKNOWN`, and `BLOCKED`
- monotonic expansion
- budget-approval requirements
- explicit opened, rejected, and omitted context items
- stable semantic error codes

AIOS-Tools already implements deterministic Retrieval Trajectories and Cognition Receipts. The missing executable seam is a read-only adapter that converts one validated Retrieval Trajectory into one validated Context Expansion Decision Record.

## Current research delta

The research found one genuine knowledge gap: the frozen contract names a sufficiency verdict, but does not prescribe how evidence sufficiency should be represented before a runtime emits that verdict.

Relevant primary sources:

- SURE-RAG treats sufficiency as a set-level property and separates support, conflict, coverage, disagreement, and uncertainty instead of trusting independent passage scores: https://arxiv.org/abs/2605.03534
- AB-RAG shows that adaptive retrieval should be budget-aware and should stop or expand based on explicit evidence and uncertainty signals rather than a fixed top-k count: https://arxiv.org/abs/2606.29090
- OpenViking independently demonstrates L0/L1/L2 progressive loading and preserved retrieval trajectories: https://github.com/volcengine/OpenViking
- Temporal replay guidance reinforces that nondeterministic observations must be recorded as history rather than recomputed during replay: https://github.com/temporalio/sdk-python

## Decision

Do not add an opaque model judge, learned confidence threshold, or new authority state.

This slice introduces an execution-local `SufficiencyAssessment` with explicit set-level signals:

- required claim count
- supported claim count
- unresolved conflict count
- authority blockage
- unknown-evidence state
- evidence references

The assessment is not durable authority and is not added to the frozen CEDR schema. It supplies a deterministic, validated verdict and a content-free assessment identifier referenced by the CEDR retrieval-path pointer.

## Included

- Draft 2020-12 CEDR schema
- deterministic `SufficiencyAssessment`
- consistency validation for the four existing sufficiency verdicts
- deterministic CEDR identifiers
- exact conversion from the merged Retrieval Trajectory contract
- explicit authority-role mapping without authority transfer
- opened and rejected packet lineage
- optional omitted-item lineage
- existing stable semantic errors:
  - `CEDR_MISSING_SUFFICIENCY`
  - `CEDR_UNAPPROVED_BUDGET_INCREASE`
  - `CEDR_ILLEGAL_TIER_TRANSITION`
- positive and negative-path tests

## Boundaries

- no live Notion, Drive, GitHub, or web connector calls
- no source writes
- no memory suppression
- no MASON promotion
- no automatic authority resolution
- no learned sufficiency scoring
- no hidden chain-of-thought capture
- no MCP or provider-adapter expansion
- no workflow replay implementation
- no Observatory projection
- no Active promotion

## Runtime flow

```text
validated RetrievalTrajectory/0.1
  → explicit set-level SufficiencyAssessment
  → ContextExpansionDecisionRecord/0.1
  → ordinary AIOS-Tools execution or later workflow receipt
```

## Validation

Local isolated proof before repository write:

```text
7 passed
```

The full repository CI remains the merge gate. No claim is made that GitHub Actions passed until the branch workflow completes.

## Next gate

After CI and review:

1. expose the adapter through one bounded read-only packet workflow;
2. attach its record identifier to the existing Cognition Receipt evidence surface;
3. project the record into the Observatory without copying raw source content;
4. keep Memory Correction Tombstone, replay compatibility, and validation-link runtime work as separate slices.
