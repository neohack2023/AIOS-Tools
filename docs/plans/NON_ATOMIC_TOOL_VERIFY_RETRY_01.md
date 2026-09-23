# NON_ATOMIC_TOOL_VERIFY_RETRY_01

## Source

Legacy Notion backlog prototype:
BACKFILL PROTOTYPE — NONATOMIC_TOOL_VERIFY_RETRY_FIXTURE_01 — v0.1

Scope: global-working-memory.

## Feature

Deterministic retry-decision engine for external or otherwise non-atomic tool calls.

The module does not perform retries. It only decides whether a retry is legal after a caller supplies dispatch, acknowledgement, postcondition, idempotency, composite-effect, and scope observations.

## Decisions

- COMPLETE_NO_RETRY
- RETRY
- REPAIR_ONLY
- BLOCK

## Laws

- ACK_AMBIGUOUS never maps directly to success or retry.
- Ambiguous acknowledgements require explicit postcondition evidence.
- Confirmed prior effect suppresses retry.
- Unknown verification blocks unless a provider-native idempotency contract makes replay safe and policy permits it.
- Partial or malformed composite effects never trigger a blind full retry.
- Partial effects may emit REPAIR_ONLY only when a bounded repair path is explicitly available.
- Recovery cannot change the prepared scope.
- Every decision emits a deterministic content-addressed receipt.

## Pre-implementation evaluation

The policy was evaluated before repository implementation against ten sealed scenarios:
timeout before dispatch, lost ACK after effect, delayed visibility, partial write, idempotent replay, no postcondition/no idempotency, missing composite child, wrong composite relationship, lost ACK after complete composite creation, and bounded repair of a partial graph.

Result: 10/10 PASS.

## Non-goals

- executing tool calls;
- performing retries;
- provider-specific network adapters;
- generic workflow orchestration;
- automatic repair;
- widening authority, target, scope, or tool set.

This is a legality/decision boundary only.
