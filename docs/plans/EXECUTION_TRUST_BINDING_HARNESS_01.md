# EXECUTION_TRUST_BINDING_HARNESS_01

## State

`AUTHORIZED_BY_DIRECT_USER_REQUEST / EXPERIMENTAL / DISPOSABLE`

Governing contract: `AIOS_EXECUTION_TRUST_BINDING_01 — Promoted Prototype`

Prior MASON plan: `MASON-20260903-GLOBAL-EXECUTION-TRUST-BINDING-01`

Prior plan digest:
`SHA256:1756bd21af19c3d60f57d505a94ff2d76b37fd6bfd1849d2067a778a65737bf1`

Repository base: `neohack2023/AIOS-Tools@8ac990db4bf9f397b6caa5c367193eec3a9d846a`

## Purpose

Implement the contract's frozen ETB-01 through ETB-10 matrix as a removable
experimental harness, then prove that one existing real read-only executor/tool
path is invoked only after a complete trust admission.

## Scope

- one strict JSON Schema for the experimental binding envelope;
- one deterministic trust evaluator with fail-visible reason codes;
- one frozen overlay-based ETB fixture matrix;
- one command-line harness that can run the matrix and gate `system.health`;
- tests for all ten cases, schema failure, denial-before-executor, and the real
  read-only path;
- retained console/PR evidence from the exact tested commit.

## Non-goals

- no production runner interception or registry/policy activation;
- no new tool registration or capability state change;
- no write-capable, credential-bearing, extension, browser, or network live run;
- no Notion, Drive, deployment, auto-merge, canon, Trusted Memory, or semantic
  authority mutation;
- no automatic skill installation;
- no claim that security trust grants semantic authority.

## Admission law

The harness returns one of `ADMIT`, `BLOCK`, `PENDING_POLICY`, `STALE`, or
`UNKNOWN`. Only `ADMIT` may invoke the supplied executor. Material identity,
catalog, policy, consent, dependency, topology, egress, extension, semantic
authority, or held-out validation failures remain visible in deterministic
reason codes. The harness never transfers authority.

## Real path

The sole live verification target is the existing shared-core Python path:

```text
trust binding preflight
  -> aios_tools.runner.invoke
  -> system.health
  -> ordinary AIOS execution receipt
```

The bound request is `READ_ONLY` with `NO_EXTERNAL_EFFECT`; the expected tool
receipt has `status=COMPLETED`, `external_effects=[]`, and
`authority_transfer=false`.

## Validation

```bash
python -m pip install -e ".[dev]"
pytest
aios-tools list
aios-tools invoke system.health --input '{}'
aios-tools-mcp --help
python scripts/run_execution_trust_binding.py --real-read-only
```

## Risks and containment

- The envelope is experimental and may diverge from a later production
  supervisor contract. Containment: no normal runner or adapter imports it.
- A fixture could pass without proving a real path. Containment: the harness
  invokes the unchanged shared core only after ETB-10 admission and preserves
  both receipts.
- A security PASS could be misread as authority. Containment: the result copies
  the exact semantic destination and always preserves the contract's promotion
  flag; no evaluator rule can raise it.

## Rollback

Close the draft PR and delete the branch, or remove the experimental module,
schema, fixtures, script, tests, plan, and README paragraph as one unit. No
production registry, policy, handler, adapter, or external authority surface is
changed.
