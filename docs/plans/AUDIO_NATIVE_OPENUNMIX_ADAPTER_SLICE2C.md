# AUDIO_NATIVE_OPENUNMIX_ADAPTER — Slice 2C

## Status

`CANDIDATE / NATIVE ADAPTER IMPLEMENTED / PILOT EXECUTION BLOCKED BY NATIVE TIMEOUT / NOT RUNTIME ADMITTED`

## Decision

Use the upstream `umx` executable as the separation engine. AIOS-Tools owns only the invocation contract, process boundary, timeout, source verification, output-set validation, receipts, and promotion boundary.

## Frozen invocation

```text
umx <source>
  --model umxhq
  --targets vocals drums bass other
  --outdir <isolated-stage>
  --ext wav
  --niter 1
  --wiener-win-len 300
  --filterbank torch
  --verbose
  --no-cuda
```

## Dependency lock

- `openunmix==1.3.0`
- wheel SHA-256 `e893ae22c5b8001a6107022499c2587b70d5c2e4777cc7c9ed6272b68a69534e`
- UMXHQ model weights remain the four Slice 2A locked artifacts
- analysis network access disabled

## Adapter responsibilities

- verify executable presence
- verify source SHA-256
- construct an argv list without shell interpretation
- isolate native outputs in a staging directory
- enforce a process-group timeout
- terminate and then kill the complete process group if required
- preserve stdout, stderr, return code, elapsed time, and failure code
- require exactly one vocals, drums, bass, and other artifact
- hash and size every promoted stem
- atomically promote only a complete output set
- preserve failed execution evidence separately

## Pilot

Track: `L04D-B34R1NG_SP4RK`

- source SHA-256: `3a1573821ed5ef792014bd5945cf4ca298c8f11b71a9088c65e207834ee5ae7e`
- source bytes: `6904230`
- environment: Python `3.13.5`, Open-Unmix `1.3.0`, PyTorch `2.10.0+cpu`, Torchaudio `2.10.0+cpu`, NumPy `2.3.5`
- native executable: `/opt/pyvenv/bin/umx`
- timeout: `900 seconds`
- result: `NATIVE_PROCESS_TIMEOUT`
- promoted stems: none
- partial output promotion: false

The native upstream path still failed the full-track bounded-execution requirement in the available CPU environment. This is evidence for evaluating a second native engine or a native execution mode with upstream segmentation support. It is not authorization to restore custom chunking.

## Boundary

`runtime_admission=false`

`pilot_authorized=false`

`authority_transfer=false`
