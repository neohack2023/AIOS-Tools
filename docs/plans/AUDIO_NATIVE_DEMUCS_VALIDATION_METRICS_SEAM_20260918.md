# AUDIO_NATIVE_DEMUCS_VALIDATION_METRICS_SEAM — 2026-09-18

Status: IMPLEMENTATION_CANDIDATE / CURRENT_MAIN_BASED / NO_AUTHORITY_WIDENING

## Objective

Carry the two surviving evidence guarantees from PR #36 onto the current native Demucs adapter:

1. validate the actual promoted WAV encoding and shape instead of trusting requested output flags;
2. compute normalized reconstruction/stem-activity metrics and freeze them into durable run evidence before promotion.

## Governing evidence

- Drive contract: FAILURE_EVIDENCE_CAPSULE_RESEARCH_DECISION_01
- Live PR #36 replay successor capsule: fec:sha256:413e2522ed8c3ec4bf8fe31858aa7b4dd4d46a2292ad2772be9a2a7834c78baf
- Durable decision: preserve PR #36 as an evidence donor; implement on the current native-adapter lane.

## Exact base

Repository: neohack2023/AIOS-Tools
Base branch: main
Base SHA: 45ed34523cf0915591dce73a2101c32cf91dc891
Candidate branch: agent/demucs-validation-metrics-seam

## Scope

Modify only the current native Demucs seam and its evidence/tests/documentation.

Planned paths:
- src/aios_tools/audio_native_demucs.py
- tests/test_audio_native_demucs.py
- pyproject.toml (dev-only NumPy test dependency)
- docs/workflows/AUDIO_DEMUCS_AI0S_USAGE.md
- this plan

## Non-goals

- no resurrection or merge of PR #36 as the permanent separator;
- no custom AIOS-owned chunking or overlap-add;
- no Demucs model/profile change;
- no registry or execution-policy widening;
- no runtime_admission or pilot_authorized promotion;
- no connector/network/credential expansion;
- no merge, release, or deploy authority.

## Implementation slices

### Slice A — Actual WAV validation

After native Demucs returns a complete four-stem set and before atomic promotion:

- parse RIFF/WAVE chunks with stdlib only;
- require IEEE-float WAV format code 3;
- require stereo;
- require 44,100 Hz;
- require 32 bits/sample and block_align 8;
- derive exact frame count from data bytes;
- require all four stems to have identical frame counts.

Verifier obligations:
- valid float32 stereo fixture passes;
- PCM16 fixture fails closed;
- frame-count mismatch fails closed;
- no invalid output can be promoted.

### Slice B — Normalized quality metrics

Decode the source and verified stems with the exact Demucs 4.1.0 loader order used by separation: `sphn.read()` first, then `AudioFile`/ffmpeg fallback, normalizing to stereo 44.1 kHz, then compute:

- reconstruction RMS error;
- residual-to-mix energy ratio;
- per-stem one-second RMS/peak activity windows;
- exact sample rate/channel/sample-count facts.

The helper mirrors the pinned Demucs loader backend order, records the source's original sample rate, normalizes the evidence stream to stereo 44.1 kHz, and fails closed when dependencies are unavailable or decoded shapes/rates/durations disagree. This prevents metrics from comparing a differently decoded MP3 timeline than the one Demucs actually separated.

Verifier obligations:
- deterministic synthetic arrays prove energy-ratio semantics;
- non-normalized stem rate, invalid shape, or duration mismatch fails closed;
- a 48 kHz source is normalized through the pinned Demucs audio reader and recorded as resampled;
- tests do not depend on an actual model download.

### Slice C — Durable evidence freeze

Before promotion write inside the isolated stage:

- analysis/stem-metrics.json
- stdout.log
- stderr.log
- run-receipt.json

The receipt records profile/source identity, command, elapsed time, actual WAV validation, metrics pointer/summary, stem hashes, and authority/runtime boundaries. The returned artifact manifest hashes stems plus evidence files.

Verifier obligations:
- receipt and metrics exist before stage promotion;
- artifact manifest includes their SHA-256 and byte counts;
- authority_transfer=false and runtime_admission=false remain explicit.

### Slice D — Current-head verification and pilot

1. Open a draft PR to main.
2. Verify AIOS-Tools CI and Repository Governance on the exact candidate head.
3. Only after exact-head CI passes, replay the same L04D-B34R1NG_SP4RK source under the pinned Demucs profile on an authorized runtime surface.
4. Record actual stem format, metrics, receipt identity, elapsed time, and any failure.
5. Keep pilot result as evidence; do not infer runtime admission.

## Rollback

The change is branch-local until human merge. Revert the candidate branch/PR if:
- validation rejects known-good pinned Demucs output;
- metrics cannot be reproduced deterministically;
- evidence generation causes partial promotion;
- CI exposes unrelated runtime coupling;
- same-track replay contradicts the prior pinned profile evidence.

## Acceptance

Implementation candidate is acceptable for review only when:
- focused tests pass;
- full current-head CI passes on the exact candidate SHA;
- governance CI passes on the exact candidate SHA;
- no authority or policy widening occurs.

Pilot replay is a separate evidence step after CI.
