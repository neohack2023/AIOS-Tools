# DAILY_DEBRIEF_RECOVERY_01

## Slice

Issue #80, finding 5 of 7: deterministic crash, retry, and replay recovery.

## Purpose

Prove that the Daily Debrief pipeline remains correct when execution stops between durable append, projection, and acknowledgement.

## Research basis

Cloudflare Queues provides at-least-once delivery by default and explicitly notes that a message may be delivered more than once. Its guidance recommends stable unique IDs / idempotency keys for deduplication.

Cloudflare also states that queue delivery order is not guaranteed.

Amazon SQS likewise documents at-least-once delivery and recommends idempotent consumers because duplicate copies can be delivered.

References:
- https://developers.cloudflare.com/queues/reference/delivery-guarantees/
- https://developers.cloudflare.com/queues/reference/how-queues-works/
- https://docs.aws.amazon.com/AWSSimpleQueueService/latest/SQSDeveloperGuide/standard-queues-at-least-once-delivery.html

## Recovery order

The recovery model is:

1. validate/adapt;
2. durably append accepted evidence;
3. project durable events;
4. acknowledge upstream delivery.

If execution stops after step 2, replay catches the projection up.

If execution stops after step 3 but before acknowledgement, upstream redelivery becomes an event-store `DUPLICATE_NOOP`; projection recovery starts after its checkpoint sequence and therefore does not double-count.

## Helpers

`ingest_structured_debrief(...)`
- adapts structured input;
- quarantines adapter rejection;
- appends valid events through the append-only event store;
- does not project implicitly.

`recover_projection(event_store, checkpoint=None)`
- starts empty or from a validated projection checkpoint;
- fails closed if the checkpoint is ahead of durable evidence;
- applies only events after the checkpoint sequence.

## Recovery laws

The regression suite proves:

1. exact duplicate delivery is a no-op;
2. crash after append before projection recovers by replay;
3. crash after projection before acknowledgement does not double-count;
4. deleting projection state and replaying all durable events yields the same projection digest;
5. out-of-order projection input fails closed;
6. future schema input is quarantined and never enters accepted evidence;
7. resolving one gate changes only that exact gate ID;
8. two writers using the same expected event sequence cannot both commit;
9. a projection checkpoint ahead of durable evidence fails closed.

## Boundary

This slice does not:
- guarantee external queue ordering;
- auto-redrive quarantine;
- introduce a hosted queue consumer;
- run the seven-debrief historical evaluation;
- generate implementation-plan handoffs;
- promote Canon / Trusted Memory / runtime authority.

Those remain findings 6 and 7 under issue #80.
