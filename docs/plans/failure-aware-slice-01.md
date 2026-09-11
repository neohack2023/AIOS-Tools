# Failure-aware slice 01: offline continuation validation

Base: `df0d9178656a0e2c91ae2d787fe4ab8c82758236`.
Owner exception: direct-to-main delivery authorized in the active conversation
only if checks pass; no production activation or capability widening.
Upstream: https://app.notion.com/p/3d543bd4ae4a819aace8da8c0f5ed347

Implement an experimental pure function over two explicit boundary snapshots.
It checks immutable-prefix, artifact/receipt, envelope, specialist-history,
current-evidence and retry invariants before returning one advisory action.
Caller attestations are not authenticated: this is an offline evaluator, not
an authorization verifier or a scheduler. No registry/policy/handler changes.

Paths: experimental module, focused tests, this plan. No existing files changed.
Required checks: focused malformed/boundary/regression tests; repository pytest;
CLI/MCP smoke; repository governance checks. Freeze exact candidate before
verification. Do not publish on failed required checks. Record a checkpoint
before beginning attribution or memory-probe implementation.

Rollback: revert the slice commit; no external state or memory was changed.
Live replay and outcome/cost gains remain pending.
