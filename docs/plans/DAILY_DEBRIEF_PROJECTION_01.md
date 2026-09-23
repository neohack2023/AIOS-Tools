# DAILY_DEBRIEF_PROJECTION_01

## Slice

Issue #80, finding 3 of 7: rebuildable materialized Daily Debrief digest projection.

## Purpose

Build queryable current digest state strictly from the immutable Daily Debrief event stream.

The event store remains the source of truth. The projection is disposable and rebuildable.

## Research basis

Microsoft's Materialized View pattern states that a materialized view should be treated as disposable because it can be rebuilt from source data, and applications should not update it directly.

Microsoft's Event Sourcing guidance similarly treats projections as read-only views derived by replaying ordered events; snapshots are an optimization and do not replace the event stream.

References:
- https://learn.microsoft.com/en-us/azure/architecture/patterns/materialized-view
- https://learn.microsoft.com/en-us/azure/architecture/patterns/event-sourcing
- https://learn.microsoft.com/en-us/azure/architecture/patterns/cqrs

Cloudflare's SQLite-backed Durable Object storage remains compatible with later durable projection snapshots because it provides transactional, strongly consistent storage, but no hosted binding is added in this slice:
- https://developers.cloudflare.com/durable-objects/api/sqlite-storage-api/

## Projection contract

`DailyDebriefProjectionState` carries:
- projection revision;
- last applied event sequence;
- processed event IDs;
- per-lineage accumulated consequences and validation evidence;
- unresolved and resolved exact test gate IDs;
- simulation/live verification counts.

## Sequence law

`project_event` accepts only the next contiguous event sequence.

If projection state says sequence 12 was last applied, only sequence 13 may be projected next.

Gaps, duplicates, or stale replay against the same mutable state fail closed.

## Rebuild law

`rebuild_projection(events)` starts from empty state and replays the ordered event stream.

Required invariant:

`canonical(incremental_state) == canonical(full_rebuild_state)`

The regression suite checks both payload equality and canonical digest equality.

## Gate law

Gate state follows ordered explicit evidence.

If an event marks a gate unresolved, the gate is placed in the unresolved set and removed from the resolved set. If a later event resolves that exact gate, the inverse occurs. A still-later explicit unresolved event may reopen it.

Absence of a gate ID in an event does not change that gate's state.

## Projection identity

`projection_digest(state)` uses the repository's canonical SHA-256 helper over the normalized projection payload.

`projection_envelope(state)` attaches that digest for checkpoint/tamper verification.

## Boundary

This slice does not:
- persist projection checkpoints independently;
- add quarantine/dead-letter storage;
- repair gaps automatically;
- skip missing event sequences;
- perform seven-day replay evaluation;
- generate implementation handoffs;
- promote any authority state.

Those remain findings 4 through 7 under issue #80.
