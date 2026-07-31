# Official Benchmark Environment

AIOS-Tools owns the executable benchmark harness. Notion remains architecture and governance authority. Google Drive and the Operations Ledger remain evidence and reporting surfaces.

## Classification boundary

Every run must be labeled as exactly one of:

- `OFFICIAL_FULL_RUN`: upstream evaluator executed against an immutable upstream commit with native result artifacts captured.
- `PROTOCOL_SMOKE`: a bounded local test inspired by a public benchmark.
- `STANDARDS_CONFORMANCE`: deterministic validation against a specification or test suite.
- `HUMAN_REVIEW`: rubric-based evidence review with no claim of automated benchmark parity.

A run may not be promoted from one class to another by renaming a file or changing a spreadsheet cell.

## Official-run admission gates

An `OFFICIAL_FULL_RUN` is blocked unless all gates pass:

1. The upstream repository URL is the official project source.
2. `source_ref` is an immutable 40-character Git commit SHA.
3. The required runtime is present.
4. Required secrets are declared and supplied without entering logs or receipts.
5. Resource requirements are acknowledged.
6. The upstream evaluator runs without AIOS modifying its scoring implementation.
7. Native result artifacts and logs are retained.
8. The AIOS normalized receipt links to the upstream commit, command, environment, raw result artifact, and scorer version.

## Slice 2: immutable pins and execution plans

The six first-wave benchmarks are pinned to exact upstream commits. The registry loader rejects malformed immutable pins. Each entry now declares a gold check, and the execution-plan layer produces deterministic clone, detached-checkout, preparation, gold-check, and result-capture instructions.

```bash
python -m pip install -e ".[dev]"
aios-bench list
aios-bench doctor
```

The execution plan is data, not shell improvisation. External benchmark execution remains an explicit human-authorized step because several suites require model credentials, large datasets, Docker, or substantial compute.

## First-wave pins

- LongMemEval-V2: `6f020ac2fc3275e46c706d3406e02c3ed79b7be2`
- Berkeley Function Calling Leaderboard V4: `6ea57973c7a6097fd7c5915698c54c17c5b1b6c8`
- tau2-bench: `363133ada1936491fb5bcec33cd62c3518a99f65`
- AgentDojo: `089ed468cf3ed0322acc66b0211f26d9d90dbf60`
- SWE-bench Verified: `f7bbbb2ccdf479001d6467c9e34af59e44a840f9`
- JSON Schema Test Suite Draft 2020-12: `0c7b65dc16dd8eaa7bd83e21099c76610c3b246a`

Updating a pin is a benchmark registry change and must produce a fresh evidence receipt.

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
