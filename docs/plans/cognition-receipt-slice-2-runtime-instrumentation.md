# Cognition Receipt Slice 2: Runtime Instrumentation

## Objective

Attach one deterministic cognition receipt to every governed AIOS-Tools execution receipt by instrumenting the existing centralized receipt path.

## Included

- runtime execution event vocabulary
- deterministic execution cognition receipt assembly
- required cognition receipt field in the execution receipt contract
- instrumentation of completed, failed, and blocked tool runs
- validation that cognition and execution receipts share request, scope, mode, status, and timestamps
- tests for success, invalid input, policy block, and configuration block paths

## Event sequence

1. `intent.received`
2. `intent.classified`
3. `scope.candidate_considered`
4. `scope.resolved`
5. `execution.requested`
6. `execution.eligibility_evaluated`
7. `tool.invoked` when a handler is reached
8. one terminal event: `tool.completed`, `tool.failed`, or `tool.blocked`
9. `receipt.created`

## Safety boundary

- no hidden chain-of-thought
- no raw prompt capture
- no unrestricted payload or output duplication
- no source writes
- no connector instrumentation
- no live retrieval tracing
- no authority transfer
- no external effects
- no Observatory integration

## Acceptance criteria

- every `invoke()` result contains a valid cognition receipt
- blocked paths do not claim handler invocation
- completed and failed handler paths do claim handler invocation
- cognition receipt status and identifiers match the enclosing execution receipt
- existing tool outputs remain unchanged
