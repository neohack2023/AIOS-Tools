# DAILY_DEBRIEF_ADAPTER_01

## Slice

Issue #80, finding 1 of 7: structured Daily Debrief adapter.

## Purpose

Convert an already-structured Daily Debrief / STONE-MASON output into deterministic, content-addressed evidence events without granting the research packet any implementation or runtime authority.

This slice intentionally does not parse arbitrary prose.

## Research constraints

The adapter follows four external design constraints:

1. event schemas need explicit versioning because producers and consumers evolve independently;
2. duplicate delivery is expected in event-driven systems, so stable idempotency identity is required;
3. immutable event history benefits from versioned envelopes rather than in-place reinterpretation;
4. malformed or unsupported input must fail closed rather than silently mutating the downstream state.

Primary references:
- CloudEvents common event envelope: https://cloudevents.io/
- Azure event-driven schema evolution: https://learn.microsoft.com/en-us/azure/architecture/guide/architecture-styles/event-driven
- Azure event sourcing schema evolution: https://learn.microsoft.com/en-us/azure/architecture/patterns/event-sourcing
- AWS idempotent mutation guidance: https://docs.aws.amazon.com/wellarchitected/2025-02-25/framework/rel_prevent_interaction_failure_idempotent.html

## Input contract

Supported input schema:

`daily-debrief-structured/v1`

Required envelope fields:
- source_provider
- source_id
- source_revision
- source_digest
- debrief_date
- scope_key
- findings[]

Each finding requires:
- finding_id
- lineage
- title
- disposition
- confidence
- implementation_consequence
- validation_state
- remaining_test_ids[]
- resolved_test_ids[]

## Output contract

One event per finding:

`daily-debrief-finding-event/v1`

Each event is assigned:

`event_id = ddf_ + canonical_sha256(event_without_event_id)`

The implementation reuses the repository's existing `canonical_sha256` primitive.

## Fail-closed behavior

Rejected:
- unknown input schema;
- unresolved/blank scope;
- missing source identity or source revision;
- invalid source digest;
- malformed IDs;
- duplicate finding IDs in one debrief;
- the same exact test ID appearing as both unresolved and resolved;
- explicit authority-bearing keys;
- tampered event content that no longer matches its event ID.

## Compatibility posture

Unknown additive non-authority producer fields are ignored when adapting v1 input. They do not enter the normalized event and therefore cannot change the event identity.

A changed semantic field does change the event identity.

A future schema version is rejected until explicitly supported.

## Boundary

This slice does not:
- persist events;
- sequence events;
- update the digest projection;
- quarantine rejected events durably;
- replay multiple debrief days;
- generate implementation issues or PRs;
- promote Canon / Trusted Memory / Active capability state.

Those remain findings 2 through 7 under issue #80.
