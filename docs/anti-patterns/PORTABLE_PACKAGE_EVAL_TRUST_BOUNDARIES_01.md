# PORTABLE_PACKAGE_EVAL_TRUST_BOUNDARIES_01

Status: CONFIRMED_ANTI_PATTERN  
Origin: PR #72 portable package evaluation runtime repair  
Failure-learning class: SECURITY_BOUNDARY / RESOURCE_BOUNDARY / RECEIPT_INTEGRITY  
Applies to: provider transports, archive ingestion, product-surface receipts, evaluation harnesses

## Report binding

This anti-pattern was harvested from the repair pass on PR #72 after a green implementation head was found to contain trust-boundary defects during independent inspection.

Historical defective head:
`5aedbb56723d4466f37eb4a589cd16006a0b1e4d`

First repaired-and-verified head before anti-pattern capture:
`e5a67a362a8624ab58fdac971f27eb462b386781`

Evidence runs on that repaired head:
- Repository Governance #493: PASS
- Benchmark Registry #166: PASS
- AIOS-Tools CI #495: PASS
- Browser Activation Replay #95: SKIPPED / non-applicable

The executable regression source is:
`tests/test_portable_package_eval_transport.py`

Machine-readable mapping:
`fixtures/package-eval/portable-package-eval-trust-boundaries-01.json`

## AP-01: Caller-controlled credential destination

### Bad pattern

A provider wrapper accepts an arbitrary endpoint while automatically attaching a bearer credential.

### Failure mechanism

The caller can redirect credential-bearing traffic away from the intended provider. Normal HTTP redirect handling can also propagate ordinary headers to a redirected request unless explicitly constrained.

### Required invariant

Credential-bearing OpenAI package-eval requests MUST be pinned to the declared official endpoint. Authorization MUST NOT be forwarded by redirect machinery. Redirects fail closed.

### Regression fixtures

- `test_provider_transport_is_pinned_and_auth_is_unredirected`
- `test_pair_execution_rejects_non_official_credential_endpoint`

### Preventive rule

Do not combine:
`caller-controlled destination + ambient provider credential`.

If custom provider endpoints are ever supported, they require a separate explicit trust contract and credential namespace.

## AP-02: Archive limits applied after expansion

### Bad pattern

An archive member is fully read into memory and aggregate limits are checked only after the reads complete.

### Failure mechanism

Compressed input can force unbounded or unexpectedly large decompression work before the limit rejects it. Per-file checks alone do not bound aggregate expansion.

### Required invariant

Before reading selected archive members:
- bound selected text-file count;
- bound each declared uncompressed member size;
- bound aggregate declared uncompressed size.

During reads:
- read at most the governed per-file limit plus one byte;
- recheck actual aggregate bytes.

### Regression fixture

- `test_context_projection_rejects_total_zip_expansion_before_member_read`

### Preventive rule

`VALIDATE_SIZE_BEFORE_EXPANSION + RECHECK_DURING_BOUNDED_READ`.

A digest or archive validity check does not prove resource safety.

## AP-03: Shallow secret blackout

### Bad pattern

Receipt/evidence filtering checks only top-level keys for secrets.

### Failure mechanism

Sensitive material can be nested in dictionaries/lists or use normalized key variants such as `api-key`.

### Required invariant

Secret-key detection MUST recursively traverse all receipt evidence containers and normalize supported key spelling variants before comparison.

### Regression fixtures

- `test_product_surface_takeover_chain_and_secret_blackout`
- `test_product_surface_secret_blackout_is_recursive`

### Preventive rule

For structured evidence, secret filtering is recursive or it is not a blackout.

## AP-04: Insert-time-only receipt validation

### Bad pattern

Secret evidence is checked only when an event is appended, while later receipt validation trusts already-stored event bodies.

### Failure mechanism

A receipt can be mutated after insertion, bypassing the original guard while still passing structural state-machine validation.

### Required invariant

Terminal receipt validation MUST independently revalidate stored evidence against the secret blackout.

### Regression fixture

- `test_product_surface_validation_rejects_tampered_nested_secret`

### Preventive rule

`VALIDATE_ON_WRITE != VALIDATE_ON_USE`.

Trust-bearing receipts need both.

## Relation to verifier-owned acceptance

A green test suite before these fixtures existed did not prove these obligations. The lesson is not "CI failed"; the lesson is that verifier coverage was incomplete.

Future package-eval acceptance should explicitly bind these obligations:
1. credential destination integrity;
2. redirect credential containment;
3. archive expansion bounds;
4. recursive secret blackout;
5. receipt revalidation against post-write mutation.

If any of these regression fixtures are skipped, removed, renamed without an equivalent replacement, or no longer exercise the same failure mechanism, package-eval trust-boundary coverage becomes PARTIAL rather than PASS.

## Promotion boundary

This record is negative knowledge and regression guidance. It does not grant merge, release, deployment, provider, or authority permission.
