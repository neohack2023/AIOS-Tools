# PORTABLE_PACKAGE_EVAL_ACCEPTANCE_INTEGRITY_01

Status: CONFIRMED_ANTI_PATTERN  
Origin: PR #72 portable-package evaluator acceptance pass  
Failure-learning class: EVIDENCE_INTEGRITY / PROVIDER_COMPLETION / PAIR_IDENTITY  
Applies to: evaluation capsules, provider responses, paired A/B execution, grading receipts

## Why this is separate from the trust-boundary catalog

`PORTABLE_PACKAGE_EVAL_TRUST_BOUNDARIES_01` owns credential, archive-expansion, secret-blackout, and receipt-mutation failures.

This record owns a different failure family: evidence can remain structurally valid while the evaluator consumes stale capsule bytes, grades an incomplete provider response, or compares the same provider response identity twice.

Those are acceptance-integrity failures, not transport-secret failures.

Discovered against PR #72 head:

`e65e7239ae842acce38d0ab042f9eb247e0d999e`

Executable regression source:

`tests/test_portable_package_eval_acceptance_integrity.py`

Machine-readable mapping:

`fixtures/package-eval/portable-package-eval-acceptance-integrity-01.json`

## AP-05: Manifest digest without use-time revalidation

### Bad pattern

A capsule records SHA-256 digests for generated request/grader artifacts, but execution loads those files without recomputing and comparing the recorded digests.

### Failure mechanism

A request or grader can change after capsule creation while the manifest still advertises the original evidence identity. The evaluator then runs different bytes under the old capsule identity.

### Required invariant

Before any request contract is loaded for execution and before provider transport:

- `artifact_digests` must be present and non-empty;
- every bound artifact name must resolve to a local capsule filename;
- every expected digest must be a valid lowercase SHA-256;
- every bound artifact must exist;
- the current bytes must hash exactly to the manifest-bound digest.

### Regression fixture

- `test_pair_execution_rejects_tampered_capsule_artifact_before_transport`

### Preventive rule

`RECORDED_DIGEST != VERIFIED_IDENTITY`

A digest becomes evidence only when the consumer recomputes it at the trust boundary.

## AP-06: Output text mistaken for provider completion

### Bad pattern

A provider response is accepted for grading whenever it contains non-empty output text, even if its provider status says the response failed, is incomplete, or otherwise did not complete.

### Failure mechanism

Partial or failed provider output can be promoted into deterministic grading and a comparison receipt. That turns transport/provider failure into apparently valid evaluation evidence.

It can also waste the second treatment call after the first treatment has already failed.

### Required invariant

For each treatment, before grading:

- response root must be an object;
- response id must be a non-empty string;
- response status must equal `completed`.

If `PACKAGE_OFF` fails completion validation, `PACKAGE_ON` must not execute.

### Regression fixture

- `test_pair_execution_rejects_non_completed_response_before_second_treatment`

### Preventive rule

`TEXT_PRESENT != EXECUTION_COMPLETE`

Provider completion state is part of evidence identity.

## AP-07: Paired response identity replay

### Bad pattern

The evaluator accepts two completed-looking treatment payloads that carry the same provider response id.

### Failure mechanism

A stub, cache, replay layer, or faulty adapter can return the same provider result for `PACKAGE_OFF` and `PACKAGE_ON`. The grader may then compare a replay against itself while reporting a paired experiment.

### Required invariant

After both responses independently pass completion validation, their provider response ids must be distinct before text extraction, grading, or comparison.

### Regression fixture

- `test_pair_execution_rejects_replayed_response_identity`

### Preventive rule

`TWO_TREATMENTS_REQUIRE_TWO_PROVIDER_IDENTITIES`

A treatment label in local metadata cannot substitute for independent provider evidence.

## Regression ownership

The machine-readable anti-pattern fixture binds AP-05 through AP-07 to executable test names and contains a meta-regression that fails when a mapped test is removed or renamed without updating the catalog.

Passing these tests establishes only the local obligation. Exact-head repository CI is still required before the repaired PR head inherits acceptance evidence.

## Promotion boundary

This is negative knowledge for the portable-package evaluator. It does not grant merge, release, deployment, provider, package, browser, or authority permission.
