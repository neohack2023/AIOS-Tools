# DAILY_DEBRIEF_EVENT_STORE_01

## Slice

Issue #80, finding 2 of 7: append-only Daily Debrief event store.

## Purpose

Persist normalized `daily-debrief-finding-event/v1` records as durable replayable evidence while preserving strict idempotency and optimistic-concurrency laws.

The event stream is evidence history. It is not Canon, runtime authority, or an implementation command.

## Research basis

SQLite permits multiple readers but serializes writers. `BEGIN IMMEDIATE` starts the write transaction immediately, preventing a second writer from slipping between the expected-sequence check and the append.

References:
- SQLite transactions: https://www.sqlite.org/lang_transaction.html
- SQLite isolation: https://www.sqlite.org/isolation.html
- Cloudflare SQLite-backed Durable Object storage: https://developers.cloudflare.com/durable-objects/api/sqlite-storage-api/
- Cloudflare Durable Object storage guidance: https://developers.cloudflare.com/durable-objects/best-practices/access-durable-objects-storage/

Cloudflare remains a future runtime adapter target. This slice keeps the core persistence contract portable and uses Python SQLite as the reference implementation.

## Store contract

Portable interface:

- `append(event, expected_sequence=None)`
- `contains(event_id)`
- `iter_events(after_sequence=0)`
- `last_sequence()`

Reference implementation:

`SqliteDailyDebriefEventStore`

## Laws

### Append-only

The public store has no update/delete operation for accepted events.

### Idempotent duplicate

An exact existing `event_id` returns `DUPLICATE_NOOP` and the original sequence.

Duplicate detection occurs before expected-sequence conflict checking. This permits a producer to safely retry an append after losing the acknowledgement even when its original expected sequence has since become stale.

### Monotonic sequence

Accepted new events receive a monotonically increasing sequence.

### Optimistic concurrency

When `expected_sequence` is supplied, it must equal the current committed last sequence for a new event.

Mismatch raises `EventStoreConcurrencyConflict`.

### Atomic acceptance

The SQLite implementation uses `BEGIN IMMEDIATE` around duplicate lookup, expected-sequence verification, and insert. Acceptance and assigned sequence therefore commit atomically.

### Read integrity

Stored event JSON is reparsed and revalidated through the finding-event validator. Direct backing-store corruption fails closed with `EventStoreCorruption`.

## Boundary

This slice does not:
- mutate the Daily Debrief digest projection;
- checkpoint projection state;
- add the durable quarantine/dead-letter lane;
- perform seven-day replay evaluation;
- generate implementation-plan handoffs;
- add Cloudflare Durable Object bindings.

Those remain findings 3 through 7 under issue #80.
