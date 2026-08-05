# AUDIO_NATIVE_DEMUCS_EVALUATION — Slice 2D

## Status

`CANDIDATE / NATIVE DEMUCS ADAPTER IMPLEMENTED / PILOT EXECUTION PENDING / NOT RUNTIME ADMITTED`

## Selection

Evaluate the upstream Demucs execution path because it already owns segmentation, overlap, resampling, model inference, and audio output. AIOS-Tools retains only the governed process boundary.

## Upstream pin

- package: `demucs==4.1.0`
- wheel SHA-256: `4916a804702033ce934a6cdfa7e38dde03f7a7a6e85f41d0120eefe9e2966758`
- model: `htdemucs`
- license: MIT

## Frozen invocation

```text
python -m demucs
  --name htdemucs
  --device cpu
  --jobs 1
  --segment 7.8
  --overlap 0.10
  --shifts 0
  --out <isolated-stage>
  --filename {stem}.{ext}
  --float32
  <source>
```

## Why this lane

The upstream API and CLI expose native split, segment, overlap, device, job, and shift controls. This allows the resource envelope to be bounded without restoring AIOS-owned chunking or overlap-add.

## Adapter responsibilities

- verify exact source SHA-256
- verify the pinned executable environment
- construct argv without shell interpretation
- force offline execution
- isolate output staging
- enforce process-group timeout and cancellation
- capture stdout, stderr, exit status, and elapsed time
- require exactly four expected stems
- hash and size promoted outputs
- promote only complete output sets
- preserve failure evidence without partial promotion

## Pilot gate

Run the same `L04D-B34R1NG_SP4RK` source only after:

1. PR #39 is merged or this stacked branch is intentionally reviewed as a unit.
2. Demucs 4.1.0 and the selected model artifacts are fetched into controlled quarantine.
3. Package and model hashes are recorded.
4. CI validates the frozen command and failure paths.

The pilot must report one of:

- `COMPLETE`
- `NATIVE_PROCESS_TIMEOUT`
- `NATIVE_PROCESS_FAILED`
- `OUTPUT_SET_INVALID`
- `DEPENDENCY_LOCK_FAILED`

No fallback to custom chunking is permitted during the run.

## Boundary

`runtime_admission=false`

`pilot_authorized=false`

`authority_transfer=false`
