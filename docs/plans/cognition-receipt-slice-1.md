# Cognition Receipt Slice 1

## Purpose

Create the smallest executable foundation for inspectable AIOS cognition without storing hidden chain-of-thought or granting new authority.

## Governing sources

- AIOS Tools Execution Layer Contract
- AIOS Cognition Receipt Contract v0.1
- AIOS Cognition Receipt Slice 1 Implementation Spec

## Included

- JSON Schema Draft 2020-12 receipt contract
- deterministic SHA-256 receipt and event identities
- ordered immutable-style builder surface
- semantic transition and reference validation
- fail-closed negative-path tests

## Receipt chain

```text
request
→ intent
→ scope candidates and resolution
→ authority candidates and selection
→ retrieval candidates and decisions
→ conflict observations
→ context packet composition
→ answer reference
→ outcome observation
```

## Privacy boundary

The receipt stores classifications, decisions, evidence pointers, and output references. It must not store hidden reasoning, unrestricted source content, connector credentials, secrets, or internal chain-of-thought.

## Authority boundary

- Notion remains architecture and governance authority.
- Google Drive remains evidence and shadow surface.
- GitHub owns executable implementation truth.
- Receipts report authority decisions but cannot create or transfer authority.
- `external_effects` must remain empty.
- `authority_transfer` must remain false.

## Deferred

- live runtime instrumentation
- connector ingestion
- Observatory rendering
- conflict reconciliation
- answer quality scoring
- workflow activation
- Active promotion
