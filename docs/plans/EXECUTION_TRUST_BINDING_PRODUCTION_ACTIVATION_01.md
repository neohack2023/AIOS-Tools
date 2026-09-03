# EXECUTION_TRUST_BINDING_PRODUCTION_ACTIVATION_01

## State

`AUTHORIZED_BY_DIRECT_USER_REQUEST / ACTIVE_CANARY_TARGET / FAIL_CLOSED`

Governing contract: `AIOS_EXECUTION_TRUST_BINDING_01`

Supervisor refinement: `AIOS_TOOLS_EXECUTION_SUPERVISOR_01 — v0.1`

Implementation evidence: PR #56, merged as
`ad866a91eea46e91cdbb4dd9af073f64b62601d4`

Activation base: `neohack2023/AIOS-Tools@ad866a91eea46e91cdbb4dd9af073f64b62601d4`

## Decision

Promote the validated trust evaluator into the shared runtime and enforce it
for the existing `system.health` path. This is the only real path covered by
the exact-head evidence from the disposable harness, so production activation
is limited to that read-only, `NO_EXTERNAL_EFFECT` canary.

## Runtime law

- construct the binding inside the shared runner after ordinary request,
  registry, mode, effect, and authority checks;
- compare observed handler, request schema, metadata, dependency manifest,
  registry, and policy identity with policy-pinned expectations;
- require `trust_decision=ADMIT` before handler invocation;
- return `BLOCKED` with a fail-visible trust receipt on drift, uncertainty, or
  evaluation failure;
- include the trust receipt in the ordinary execution receipt;
- preserve `authority_transfer=false` and zero external effects.

## Explicit exclusions

- no activation for write, credential-bearing, browser, network, upload,
  durable-consumption, extension, generated-artifact, or skill-install paths;
- no hosted deployment, secret, OAuth, Notion write, Drive write, or new tool;
- no semantic, Canon, or Trusted Memory authority;
- no change to the global external-network or authority-transfer laws.

## Acceptance

```bash
python -m pip install -e ".[dev]"
pytest
aios-tools list
aios-tools invoke system.health --input '{}'
aios-tools-mcp --help
python scripts/run_execution_trust_binding.py --real-read-only
```

The exact activation head must pass hosted CI and repository governance before
merge. Post-merge `system.health` must read back `ACTIVE_CANARY`, `ADMIT`,
`READ_ONLY`, `NO_EXTERNAL_EFFECT`, no external effects, and no authority
transfer.

## Rollback

Revert the activation commit. Do not weaken `required_decision`, change
`fail_behavior`, or broaden `enforced_tools` as a rollback mechanism.
