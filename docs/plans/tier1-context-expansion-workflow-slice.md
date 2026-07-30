# Tier 1 Context Expansion Packet Workflow Slice

## Status

Candidate implementation on `agent/tier1-context-expansion-workflow`.

Scope: `global-working-memory`

Mode: `READ_ONLY`

Authority transfer: forbidden.

## Governing gate

This slice implements the next gate recorded after PR #16 merged:

1. accept one already-finalized Retrieval Trajectory;
2. invoke the merged Context Expansion Decision Record adapter;
3. emit one Cognition Receipt for the bounded packet workflow;
4. attach the CEDR identifier to the existing event evidence surface;
5. preserve zero external effects and zero authority transfer.

## No new knowledge gap

No additional external research was required. The architecture, sufficiency representation, CEDR contract, Retrieval Trajectory, and Cognition Receipt already exist. This slice is integration plumbing, not a new retrieval doctrine or governance contract.

## Runtime flow

```text
finalized RetrievalTrajectory/0.1
  → explicit SufficiencyAssessment/0.1
  → merged ContextExpansionDecisionRecord/0.1 builder
  → content-free CEDR evidence pointer
  → CognitionReceipt/0.1 event evidence
  → bounded workflow result
```

## Included

- `run_context_expansion_packet_workflow`
- one fixed workflow identity and version
- trajectory event projection into the Cognition Receipt
- CEDR evidence attachment on `context.packet_composed`, `outcome.observed`, and `receipt.created`
- content-free evidence pointers rather than embedded CEDR bodies
- deterministic output when inputs and timestamps are identical
- fail-closed validation for missing finalized trajectory identity
- fail-closed validation for missing CEDR evidence correlation
- existing Cognition Receipt and CEDR schema validation tests

## Explicit boundaries

- no Notion, Drive, GitHub, or web connector calls
- no source retrieval
- no capability registration
- no tool-registry or policy change
- no CLI command
- no MCP tool exposure
- no live workflow activation
- no durable write
- no memory suppression or promotion
- no automatic authority resolution
- no raw source content copied into receipt evidence
- no workflow replay
- no Observatory projection
- no Active or canon promotion

## Evidence-link rule

The Cognition Receipt may reference the CEDR only through a bounded pointer containing:

- evidence type
- CEDR identifier
- schema version
- scope key
- lifecycle state
- `authority_transfer: false`

The CEDR body remains a separate workflow artifact. The evidence pointer must not embed opened items, rejected items, authority-source lists, or source content.

## Validation gate

Repository CI must prove:

- existing tests remain green;
- the new workflow tests pass;
- both existing JSON schemas validate the emitted artifacts;
- the workflow result reports no external effects;
- the CEDR identifier appears on the Cognition Receipt evidence surface;
- removal of the evidence link fails closed;
- no registry, policy, CLI, MCP, or connector file changes occur.

## Next eligible gate

After CI, review, and merge, the next separately governed slice may project the existing receipt and CEDR pointer into an Observatory read model. That later slice must remain read-only and must not expose raw source content or imply runtime authority promotion.
