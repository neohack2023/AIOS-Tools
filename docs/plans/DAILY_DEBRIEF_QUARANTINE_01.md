# DAILY_DEBRIEF_QUARANTINE_01

## Slice

Issue #80, finding 4 of 7: durable rejection / quarantine lane.

## Purpose

Isolate Daily Debrief inputs that fail validation so they cannot mutate the accepted evidence stream or the materialized projection, while preserving enough bounded provenance to diagnose and deliberately reprocess them later.

## Research basis

Cloudflare Queues sends messages to a dead-letter queue after the configured retry limit is reached. Without a configured DLQ, repeatedly failing messages are eventually deleted. The DLQ is independently consumable.

AWS SQS likewise describes DLQs as a place to isolate messages that could not be processed successfully so operators can diagnose failures and explicitly redrive them later.

References:
- https://developers.cloudflare.com/queues/configuration/dead-letter-queues/
- https://developers.cloudflare.com/queues/configuration/batching-retries/
- https://docs.aws.amazon.com/AWSSimpleQueueService/latest/SQSDeveloperGuide/sqs-dead-letter-queues.html
- https://docs.aws.amazon.com/AWSSimpleQueueService/latest/SQSDeveloperGuide/capturing-problematic-messages.html

The AIOS adaptation is deliberately stricter than a generic DLQ: rejected source content is not copied into the quarantine receipt. The receipt stores provenance and hashes only.

## Receipt contract

Schema:

`daily-debrief-quarantine-receipt/v1`

Stored fields:
- rejection ID;
- rejection code;
- source provider;
- source ID;
- source revision;
- exact scope when available;
- observed schema;
- observed event ID when available;
- canonical payload digest when computable.

No findings body, source prose, credentials, raw payload, prompt text, or arbitrary producer metadata is persisted.

## Rejection classes

- `UNKNOWN_SCHEMA`
- `SCOPE_UNRESOLVED`
- `SOURCE_IDENTITY_MISSING`
- `SOURCE_REVISION_MISSING`
- `EVENT_DIGEST_MISMATCH`
- `OUT_OF_ORDER_SEQUENCE`
- `UNSUPPORTED_AUTHORITY_CLAIM`
- `VALIDATION_FAILED`

## Identity / replay

`rejection_id = ddq_ + canonical_sha256(receipt_without_rejection_id)`

Exact re-quarantine of the same bounded rejection is a `DUPLICATE_NOOP`.

This keeps repeated poison input from inflating the durable record while still making the rejection observable.

## Isolation law

Quarantine is physically separate from the accepted Daily Debrief event store.

A rejected payload:
1. does not receive an accepted evidence sequence;
2. does not mutate the projection;
3. may produce only a bounded quarantine receipt;
4. cannot automatically redrive itself.

## Redrive boundary

This slice intentionally provides no automatic redrive.

Future recovery tooling may:
- inspect the rejection reason;
- retrieve the original source through its authoritative provider using the preserved source identity/revision;
- repair or adapt it;
- resubmit through the normal adapter.

The quarantine receipt itself is never promoted into accepted evidence.

## Boundary

This slice does not:
- store rejected raw payloads;
- auto-retry poison inputs;
- auto-redrive;
- skip event-sequence gaps;
- run seven-day replay;
- create implementation handoffs;
- promote Canon / Trusted Memory / runtime authority.

Those remain findings 5 through 7 under issue #80.
