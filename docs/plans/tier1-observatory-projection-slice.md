# Tier 1 Observatory Projection Slice

## Status

Candidate implementation. Read-only. Not registered. Not activated.

## Governing gate

Episode 027 authorizes one separately governed read-only Observatory projection of the merged Context Expansion Packet Workflow result.

## Purpose

Compile one deterministic metadata-only read model from:

```text
Context Expansion Packet Workflow result
  -> validated Context Expansion Decision Record
  -> validated Cognition Receipt
  -> content-free CEDR evidence link
  -> Observatory projection
```

The projection makes an already-completed execution inspectable. It does not execute, retrieve, reconcile, or write.

## Existing architecture reused

- `context-expansion.packet-read-only/0.1`
- `ContextExpansionDecisionRecord/0.1`
- `CognitionReceipt/0.1`
- canonical SHA-256 identifiers
- existing read-only and no-authority-transfer laws
- existing Cartography separation between source model, view projection, and renderer
- existing runtime-telemetry rule that request, trace, receipt, execution, scope, and resource identities remain distinct

## Included fields

### Workflow state

- workflow ID and version
- status
- mode
- start and completion timestamps
- event count

### Distinct identities

- request ID
- trace ID
- Cognition Receipt ID
- execution ID only when explicitly supplied upstream
- Retrieval Trajectory ID
- context packet ID
- CEDR ID

No missing identity is synthesized from another identity.

### Context-expansion state

- current tier
- requested tier
- tier movement
- sufficiency verdict
- expansion trigger
- decision result
- budget state
- lifecycle state

### Evidence

Repeated CEDR references from the Cognition Receipt are deduplicated into one content-free evidence link. The link records only:

- evidence type and ID
- schema version
- scope
- lifecycle state
- no-authority-transfer flag
- event types that referenced the evidence

## Privacy boundary

The projection must not contain:

- receipt events or event payloads
- the raw Cognition Receipt
- the raw CEDR
- source content
- prompts
- embeddings or vectors
- opened, rejected, or omitted source-item bodies
- authority-source lists
- decision-reason prose
- hidden reasoning

The projection carries explicit false privacy flags for source content, event payloads, raw receipt, and raw CEDR inclusion.

## Runtime and authority boundary

This slice adds no:

- capability registry entry
- execution-policy change
- CLI command
- MCP tool
- connector call
- source read or write
- durable projection store
- runtime subscription
- live telemetry ingestion
- workflow activation
- authority transfer
- Active or canon promotion

## Determinism

Identical validated workflow results produce byte-equivalent projection objects and the same `op_<sha256>` projection ID.

## Files

- `src/aios_tools/observatory_projection.py`
- `contracts/observatory-context-expansion-projection.v0.1.schema.json`
- `tests/test_observatory_projection.py`
- `docs/receipts/tier1-observatory-projection-candidate.md`

## Verification gates

- projection-specific positive and negative-path tests
- JSON Schema Draft 2020-12 validation
- full AIOS-Tools CI
- Repository Governance
- human review

No passing result is claimed until GitHub reports it on the final branch head.

## Next eligible gate

After review and merge, a separately governed presentation slice may feed a checked-in Observatory projection fixture into the existing Cartography Workbench as a read-only inspection panel. That later slice must not add live runtime ingestion, connector credentials, source content, capability activation, or write controls.
