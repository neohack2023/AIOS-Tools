# Official Benchmark Environment

AIOS-Tools owns the executable benchmark harness. Notion remains architecture and governance authority. Google Drive and the Operations Ledger remain evidence and reporting surfaces.

## Classification boundary

Every run must be labeled as exactly one of:

- `OFFICIAL_FULL_RUN` — upstream evaluator executed against an immutable upstream commit with native result artifacts captured.
- `PROTOCOL_SMOKE` — a bounded local test inspired by a public benchmark.
- `STANDARDS_CONFORMANCE` — deterministic validation against a specification or test suite.
- `HUMAN_REVIEW` — rubric-based evidence review with no claim of automated benchmark parity.

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

## Commands

```bash
python -m pip install -e ".[dev]"
aios-bench list
aios-bench doctor
aios-bench doctor longmemeval-v2
```

The first slice provides registry validation and environment readiness checks. It deliberately blocks official readiness while registry entries still point at moving branches such as `main`.

## Registered first-wave benchmarks

- LongMemEval-V2
- Berkeley Function Calling Leaderboard V4
- tau2-bench
- AgentDojo
- SWE-bench Verified
- JSON Schema Test Suite Draft 2020-12

Visual and audio benchmark environments remain artifact-gated follow-up slices because their official evaluators require model checkpoints, generated image/audio sets, and heavier runtime dependencies.

## Result structure

Each executed benchmark should eventually produce:

```text
benchmark-results/<run_id>/
  run-manifest.json
  environment.json
  stdout.log
  stderr.log
  raw/
  normalized-result.json
  execution-receipt.json
```

The normalized result is a projection. The upstream raw result remains the scoring authority for an official run.

## Security and authority

- Preparation and execution are explicit human-authorized actions.
- The benchmark harness must not use `shell=True` for dynamic user input.
- Upstream source is cloned into a disposable workspace outside `src/`.
- Benchmark dependencies are isolated from the core AIOS-Tools environment.
- A passing benchmark does not grant architecture, policy, memory, or promotion authority.
