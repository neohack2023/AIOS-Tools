# BFCL V4 AIOS A/B Benchmark Bridge

## Purpose

Create the first model-facing benchmark path for AIOS-Tools. The same configured LLM is evaluated twice against the same pinned Berkeley Function Calling Leaderboard V4 cases:

1. `DIRECT`: BFCL invokes the provider model through its native OpenAI Responses function-calling handler.
2. `AIOS`: BFCL invokes the same provider model through a generated handler overlay that prepends the versioned AIOS operator profile.

BFCL owns the test data, tool schemas, response format, and scoring. AIOS owns subject identity, profile integrity, execution admission, package generation, receipts, and A/B comparison.

## Governing records

- Notion plan: https://app.notion.com/p/3ae43bd4ae4a812f98ddef3bfcb66421
- Benchmark program issue: https://github.com/neohack2023/AIOS-Tools/issues/20
- Environment implementation: https://github.com/neohack2023/AIOS-Tools/pull/21
- Operations Ledger: https://docs.google.com/spreadsheets/d/1v42LTbtL5GDKkt6cgmaZ3EaSCi0DMuC5KOGjrNqJ5ws/edit#gid=1986073001

## Reproducibility boundary

- BFCL source commit: `6ea57973c7a6097fd7c5915698c54c17c5b1b6c8`
- AIOS profile ID: `AIOS-OPERATOR-001-BFCL-v0.1`
- AIOS profile SHA-256: `65a864cc8851945fb19d6051d84f19ca5057cdfea5d2f3a2269acb63507f7e7a`
- API mode: `OPENAI_RESPONSES_FC`
- Provider credential: `OPENAI_API_KEY`
- BFCL model key: `AIOS_BENCH_BFCL_MODEL`
- Resource acknowledgement: `AIOS_BENCH_ACK_RESOURCE=bfcl-v4`

The first execution is an `OFFICIAL_PARTIAL_EVALUATION`, not a full leaderboard score. The exact case map and tested categories must accompany every result.

## Paired-run invariants

DIRECT and AIOS must share the same:

- BFCL commit
- provider account and API model
- native tool definitions
- exact case IDs
- temperature and BFCL generation settings
- evaluator and scoring code
- resource class
- `store=false`

The only intentional treatment difference is the declared AIOS operator profile.

## AIOS treatment implementation

The generated package creates a disposable Python overlay outside the pinned BFCL source tree:

- `aios_bfcl_handler.py` subclasses BFCL's `OpenAIResponsesHandler`.
- The handler deep-copies each case and prepends the hashed AIOS profile as a `developer` message.
- `sitecustomize.py` registers a temporary `aios::<base-model-key>` entry at interpreter startup.
- The base BFCL model configuration is copied with only its handler and display name changed.
- No BFCL evaluator or dataset file is edited.

The generated runner verifies the pinned source commit and refuses unsupported BFCL model keys.

## Case-shard resolution

A package without an explicit case map is deliberately `BLOCKED`. `select_case_shard.py` may be run inside the pinned BFCL environment to select deterministic sorted IDs. The package must then be regenerated with `--case-map` so the exact shard becomes part of the manifest.

Initial bounded categories:

- `simple`
- `parallel`
- `multiple`

A `multi_turn_base` case may be added after the single-turn gold run succeeds.

## CLI surfaces

```bash
aios-bench subjects

aios-bench subject-doctor \
  --case-map selected-case-map.json \
  --ack-resource

aios-bench package-bfcl \
  --output-dir benchmark-results/bfcl-ab \
  --case-map selected-case-map.json \
  --ack-resource
```

Execution environment:

```bash
AIOS_BENCH_BFCL_MODEL=<supported-bfcl-model-key> \
AIOS_BENCH_ACK_RESOURCE=bfcl-v4 \
OPENAI_API_KEY=<secret> \
BFCL_ROOT=<pinned-gorilla-clone> \
benchmark-results/bfcl-ab/run-bfcl-pair.sh pair
```

Credentials must be injected only at execution time. They must not be written to the package, repository, Notion, Drive, logs, or receipts.

After BFCL produces native score artifacts:

```bash
aios-bench compare-bfcl \
  --direct <direct-score.json-or-csv> \
  --aios <aios-score.json-or-csv> \
  --output benchmark-results/bfcl-ab/normalized-comparison.json
```

The normalized comparison is a projection. Native BFCL artifacts remain authoritative.

## Admission gates

Execution fails closed unless:

1. BFCL is at the pinned commit.
2. The exact case map is resolved and retained.
3. `AIOS_BENCH_BFCL_MODEL` names a model supported by the pinned BFCL configuration.
4. `OPENAI_API_KEY` is present at runtime.
5. Model-credit and CPU use are acknowledged with `AIOS_BENCH_ACK_RESOURCE=bfcl-v4`.
6. The AIOS profile exists and matches its SHA-256.
7. DIRECT and AIOS subject invariants match.
8. Output directories are isolated.
9. The upstream evaluator remains unchanged.

Admission still reports `score_status: NOT_EXECUTED` until native BFCL artifacts exist.

## Non-goals

This slice does not measure or claim:

- live Notion, Google Drive, or GitHub retrieval
- long-term memory quality
- cross-project retrieval isolation
- STONE or MASON promotion accuracy
- full BFCL leaderboard performance from a partial shard
- a score inferred from readiness metadata
- architecture, policy, memory, or authority promotion

LongMemEval-V2 requires a later live retrieval/context-packet bridge and remains a separate benchmark lane.

## Validation

The test suite must prove subject invariants, profile hash integrity, fail-closed admission, secret non-persistence, generated Python and shell syntax, blocked unresolved runners, non-score readiness, and raw-artifact authority.
