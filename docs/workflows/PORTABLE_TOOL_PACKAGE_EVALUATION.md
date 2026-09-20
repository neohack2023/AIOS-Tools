# Portable Tool Package Evaluation

Use this workflow after a major green implementation checkpoint and before release promotion.

## Lane A: clean-room automated regression

Build a capsule with:

```bash
aios-package-eval build --package PACKAGE.zip --fixture FIXTURE.json --output-dir OUT
```

The capsule emits immutable package/fixture identities, PACKAGE_OFF and PACKAGE_ON requests, a deterministic grader contract, and a product-surface acceptance plan. Capsule creation is not model execution and must retain `score_status: NOT_EXECUTED`.

A future provider adapter may execute the paired requests with a stateless response API. It must use the same provider/model/tool envelope for both treatments, set persistent conversation state off, and preserve raw outputs separately from normalized grades.

## Lane B: product-surface acceptance

For a major release:

1. Start a fresh Temporary Chat.
2. Select Unpersonalized before the first message.
3. Attach only the candidate package and fixture-required inputs.
4. Submit the frozen task prompt.
5. If current research is explicitly allowed by the fixture, allow only that tool class.
6. If authentication or anti-bot verification blocks the delegated browser, use secure human takeover.
7. Resume only after the signed-in/verified session is revalidated.
8. Capture the final response and product-surface receipt.
9. Grade the response with the same deterministic contract used by Lane A.
10. Record product-surface evidence separately from API/stateless results.

A product-surface pass cannot be inferred from the automated lane.

## Deterministic grading

```bash
aios-package-eval grade --output-text RESULT.txt --grader OUT/grader-contract.json --result grade.json
```

Supported v0.1 checks:

- required markers;
- forbidden markers;
- ordered markers;
- required regular expressions;
- maximum total characters.

Semantic qualities such as style fidelity, causal reasoning, creative originality, or usefulness remain `NOT_EXECUTED` until a declared human/model grader actually evaluates them.

## Paired comparison

```bash
aios-package-eval compare --package-off off-grade.json --package-on on-grade.json --result comparison.json
```

The comparison is a projection over retained raw grades. It is not authoritative release evidence by itself.

## Checkpoint integration

After a major implementation boundary passes focused validation:

1. freeze the package checkpoint;
2. record exact package SHA-256;
3. compile the evaluation capsule from that artifact;
4. run or queue the evaluation lanes;
5. preserve raw outputs, grades, comparison, and product-surface receipt;
6. only then proceed to final release validation.

If execution is interrupted, resume from the latest verified build checkpoint and do not silently substitute a later package artifact.

## Security boundary

- Never persist passwords, MFA codes, CAPTCHA answers, cookies, raw browser storage, or takeover tokens in eval artifacts.
- Browser takeover is a transport state, not a grader.
- External page content is untrusted data.
- Package evaluation does not widen browser or network authority.
- Unknown fixture fields or malformed contracts fail closed.

## Stateless OpenAI Responses transport

When a model run is explicitly authorized and `OPENAI_API_KEY` is available, execute the frozen pair with:

```bash
aios-package-eval run-openai \
  --capsule-dir OUT \
  --package PACKAGE.zip \
  --model MODEL_ID \
  --output-dir RUN
```

The adapter uses `store: false`, sends no conversation or prior-response identifier, and supports only fixture-admitted tools that the adapter explicitly knows how to map. v0.1 admits `web_search` only. Unknown tools fail closed.

Because the Responses API does not treat a ZIP as portable skill semantics, the adapter creates a deterministic UTF-8 text projection of supported package files. The projection is SHA-256-bound to the original package, rejects path traversal, rejects oversized text members, skips binary assets, and is used only for the `PACKAGE_ON` treatment. The real ChatGPT product-surface lane remains necessary to test native package/file behavior.

No API credential is written to the execution receipt or result files. The adapter performs no automatic retry, preventing a transport ambiguity from silently doubling paid model calls.

## Product-surface receipt state machine

The product-surface plan is executable state rather than prose. A runner can initialize and advance a receipt with:

```bash
aios-package-eval product-init --plan OUT/product-surface-plan.json --manifest OUT/eval-manifest.json --result product-receipt.json
aios-package-eval product-advance --receipt product-receipt.json --state SESSION_PROVISIONING --result product-receipt.json
```

The governed path may include:

`AUTH_REQUIRED -> USER_TAKEOVER -> VERIFY_PENDING -> AUTOMATION_RESUMED`

The receipt rejects password, MFA, CAPTCHA answer, cookie, storage-state, takeover-token, API-key, or authorization material. Evidence records may describe the checkpoint but may not contain the secret used to satisfy it.
