# Official Benchmark Environment

AIOS-Tools owns the executable benchmark harness. Notion remains architecture and governance authority. Google Drive and the Operations Ledger remain evidence and reporting surfaces.

## Classification boundary

Every run is labeled as exactly one of:

- `OFFICIAL_FULL_RUN`: upstream evaluator executed against an immutable upstream commit with native result artifacts captured.
- `PROTOCOL_SMOKE`: a bounded local test inspired by a public benchmark.
- `STANDARDS_CONFORMANCE`: deterministic validation against a specification or test suite.
- `HUMAN_REVIEW`: rubric-based evidence review with no claim of automated benchmark parity.

A run may not be promoted from one class to another by renaming a file or changing a spreadsheet cell. The JSON Schema Test Suite is classified as `STANDARDS_CONFORMANCE`; it is not represented as an official leaderboard-style benchmark.

## Readiness states

The harness keeps four states separate:

1. `registry-valid`: required fields, classifications, immutable-ref policy, and executable command contracts parse successfully.
2. `pin-ready`: the source is locked to an immutable 40-character Git commit.
3. `READY_TO_EXECUTE`: the runtime exists, required secrets are present, the resource class is explicitly acknowledged, and the benchmark has an executable gold-check contract.
4. executed result: the upstream evaluator or standards adapter has actually run and produced retained evidence.

Neither `registry-valid` nor `pin-ready` means a benchmark has executed. `aios-bench doctor` always reports `score_status: NOT_EXECUTED`; it cannot manufacture a score from environment metadata.

## Execution admission gates

Before execution, all applicable gates must pass:

1. The upstream repository URL is the official project source.
2. `source_ref` uses `IMMUTABLE_COMMIT` and is a 40-character Git commit SHA.
3. The required runtime is present.
4. Required secrets are present without entering logs or receipts.
5. The declared resource class is explicitly acknowledged with `--ack-resource`.
6. Preparation and gold-check fields are executable commands, not prose placeholders.
7. The upstream evaluator runs without AIOS modifying its scoring implementation.
8. Native result artifacts and logs are retained.
9. The AIOS normalized receipt links to the upstream commit, command, environment, raw result artifact, and scorer version.

## Slice 2: immutable pins and execution plans

The six first-wave sources are pinned to exact upstream commits. Five are classified as `OFFICIAL_FULL_RUN`; the JSON Schema source is classified as `STANDARDS_CONFORMANCE`. The registry loader rejects malformed immutable pins, unknown classifications, unsupported source-ref policies, and non-executable preparation or gold-check placeholders.

```bash
python -m pip install -e ".[dev]"
aios-bench list
aios-bench doctor agentdojo --ack-resource agentdojo
```

The doctor command still blocks until all required secrets are present. A successful doctor result is `READY_TO_EXECUTE`, never an official score.

The execution plan is data, not shell improvisation. External benchmark execution remains an explicit human-authorized step because several suites require model credentials, large datasets, Docker, or substantial compute.

## First-wave pins

- LongMemEval-V2: `6f020ac2fc3275e46c706d3406e02c3ed79b7be2`
- Berkeley Function Calling Leaderboard V4: `6ea57973c7a6097fd7c5915698c54c17c5b1b6c8`
- tau2-bench: `363133ada1936491fb5bcec33cd62c3518a99f65`
- AgentDojo: `089ed468cf3ed0322acc66b0211f26d9d90dbf60`
- SWE-bench Verified: `f7bbbb2ccdf479001d6467c9e34af59e44a840f9`
- JSON Schema Test Suite Draft 2020-12: `0c7b65dc16dd8eaa7bd83e21099c76610c3b246a`

Updating a pin is a benchmark registry change and must produce a fresh evidence receipt.

## JSON Schema standards adapter

The JSON Schema source is language agnostic and leaves runner implementation to validator authors. AIOS-Tools therefore provides an explicit adapter:

```bash
python -m aios_tools.benchmarks.json_schema_adapter \
  --suite-root . \
  --file tests/draft2020-12/type.json \
  --case-index 0
```

This adapter executes the selected required test group with `Draft202012Validator` and emits a `STANDARDS_CONFORMANCE` result. It does not claim official benchmark parity.

## Result structure

Each executed benchmark writes:

```text
benchmark-results/<run_id>/
  run-manifest.json
  environment.json
  execution-plan.json
  stdout.log
  stderr.log
  raw/
  normalized-result.json
  execution-receipt.json
```

The normalized result is a projection. The untouched upstream raw result remains the scoring authority for an official run.

## Security and authority

- Preparation and execution are explicit human-authorized actions.
- The benchmark harness must not use `shell=True` for dynamic user input.
- Upstream source is cloned into a disposable workspace outside `src/`.
- Benchmark dependencies are isolated from the core AIOS-Tools environment.
- A passing benchmark does not grant architecture, policy, memory, or promotion authority.
