# DAILY_DEBRIEF_SEVEN_DAY_EVAL_01

## Slice

Issue #80, finding 6 of 7: replay seven consecutive real Daily Debrief / STONE-MASON execution receipts.

## Frozen evaluation window

2026-09-16 through 2026-09-22, inclusive.

All seven source receipts are scoped to `global-working-memory`.

The fixture stores only normalized evaluation facts plus source IDs/revisions. It does not copy the full Drive documents into the repository. Its `source_digest` field is an evaluation-fixture identity digest derived from the date and Drive source ID, not a claim to be a raw Google Docs byte/content digest. Production ingestion must continue to use its normal source-content digest semantics.

## Source receipts

- 2026-09-16: `1HTJkbIgasvjJRRt0NcBbPxakBZ_W_M8qqhKDAhGuUvs`
- 2026-09-17: `1YNck-IRZg-ehEgtWVIVf_TVyWKBnn9wCF2uWa6EToY8`
- 2026-09-18: `1GiRM5QtpO-D8BC58yV89UGEO6MnQMxfVi8PSOAl98mc`
- 2026-09-19: `1M_c1PxdCsMbj8hxrbFHaMWFaRxQNXVH_a-7Bw1XioMk`
- 2026-09-20: `1sIFiV5b9jRKZMUZDVC5VVw9SrZIgYW2_KGyV75wmmTs`
- 2026-09-21: `1duGCyvbVVWAl-F8VdbdSqPgA5cOSvFkRxF0qJ7LB0zM`
- 2026-09-22: `1nZ140nmwSUpJHDc61yI4ekKJ-dTLU40UXPodWHOZC8k`

## Why normalization, not a prose parser

The seven durable receipts use multiple historical layouts: compact execution receipts, STONE/MASON packets, and later structured control/prototype sections.

Finding 6 is an evaluation of the durable event/projection pipeline, not a natural-language extraction benchmark.

Adding a prose parser here would couple evaluation validity to a new extraction subsystem and make the benchmark easier to overfit. The fixture therefore records a bounded, reviewable normalization of facts explicitly present in the seven receipts.

## Frozen threshold policy

The policy existed before this evaluation:

- minimum evidence events: 2;
- minimum distinct debrief days: 2;
- `READY_FOR_IMPLEMENTATION_PLAN` additionally requires at least one live PASS and zero unresolved test gates;
- repeated evidence with unresolved live tests remains `PLAN_CANDIDATE_VERIFICATION_REQUIRED`.

No threshold is tuned from this seven-day replay.

## Research guard

NIST CAISI documents two relevant agent-evaluation failure classes: solution contamination and grader gaming. Its recommendations include clear benchmark rules, preserving review evidence, closing task loopholes, and retaining held-out evaluation integrity.

For this slice that means:
- source IDs are frozen;
- the threshold is frozen before replay;
- the evaluation fixture is reviewable;
- repo logic is not allowed to inspect expected outcomes;
- the 2026-09-21 human bounded implementation addendum is recorded separately from automatic readiness.

References:
- https://www.nist.gov/caisi/cheating-ai-agent-evaluations
- https://www.nist.gov/caisi/cheating-ai-agent-evaluations/4-practices-detecting-and-preventing-evaluation-cheating

## Acceptance

The seven-day replay must prove:
- all normalized historical events are accepted without quarantine;
- incremental projection and full rebuild have the same digest;
- recurring lineages cross the evidence threshold;
- simulation-only recurring lineages do not become automatically ready;
- authority/promotion decisions agree with the seven human receipts;
- the 2026-09-21 bounded repository implementation is not mistaken for automatic authority promotion.

## Non-goals

- arbitrary historical prose parsing;
- LLM-as-grader;
- embeddings;
- threshold tuning;
- automatic repo mutation;
- automatic promotion;
- seven-day data used as training data for the same threshold.
