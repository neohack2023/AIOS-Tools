# AIOS Native Demucs Workflow

## Status

Implementation candidate. The full-track \`L04D-B34R1NG_SP4RK\` pilot completed successfully with the frozen \`htdemucs\` profile. Runtime admission remains false until PR review and CI complete.

The current validation/metrics seam is governed by \`AUDIO_NATIVE_DEMUCS_VALIDATION_METRICS_SEAM_20260918\`. It preserves the useful output-validation and quality-evidence guarantees from PR #36 on the current native-adapter architecture rather than reviving the superseded custom separator implementation.

## Registered tool

\`audio.demucs.separate\`

- mode: \`WRITE\`
- reversibility: \`PARTIAL\`
- blast radius: \`LOCAL_FILES\`
- external network effects: disabled
- authority transfer: false
- approval: required before handler invocation

## Frozen runtime

- Demucs: \`4.1.0\`
- model: \`htdemucs\`
- device: CPU
- jobs: \`1\`
- segment: \`7\` seconds
- overlap: \`0.10\`
- shifts: \`0\`
- output: float32 WAV
- profile: \`profiles/audio/demucs-htdemucs-native-cpu-v0.1.json\`

## Request file

\`\`\`json
{
  "source_path": "/absolute/path/to/source.wav",
  "output_dir": "/absolute/path/to/run-output",
  "profile_path": "/absolute/path/to/AIOS-Tools/profiles/audio/demucs-htdemucs-native-cpu-v0.1.json"
}
\`\`\`

## Approval file

\`\`\`json
{
  "approval": {
    "approved": true,
    "approved_by": "human-operator-id",
    "tool": "audio.demucs.separate",
    "scope": "udio-algorithms"
  }
}
\`\`\`

## Invocation

\`\`\`bash
aios-tools invoke audio.demucs.separate \
  --mode WRITE \
  --scope udio-algorithms \
  --authority-context @approval.json \
  --input @request.json
\`\`\`

Without a matching approval object, the runner returns \`APPROVAL_REQUIRED\` before the Demucs handler starts.

## Output validation gate

After Demucs exits successfully, but before the stage can be promoted, the adapter validates the bytes actually written to disk.

Every stem must be:

- RIFF/WAVE;
- IEEE-float format code \`3\`;
- stereo;
- \`44,100 Hz\`;
- \`32\` bits/sample;
- block-align \`8\`;
- the same exact frame count as every other stem.

The \`--float32\` command flag is configuration evidence, not proof. The parsed WAV header is the output-format evidence.

A format or frame mismatch raises a governed \`NativeDemucsError\` before promotion.

## Normalized metrics gate

The adapter decodes the source and verified stems through Demucs 4.1.0's own `AudioFile` path. The source is normalized to stereo 44.1 kHz for comparison while its original sample rate is retained as evidence. It then computes:

- reconstruction RMS error;
- residual-to-mix mean-square energy ratio;
- one-second RMS and peak activity windows for each stem;
- sample rate, channel count, and exact decoded sample count.

The metrics step fails closed if the pinned Demucs audio runtime or NumPy is unavailable, or if normalized stem rate, shape, or duration facts disagree. A 48 kHz input therefore remains admissible as source evidence while the comparison domain stays 44.1 kHz.

## Durable evidence freeze

Before atomic promotion, the staging root now contains:

- \`analysis/stem-metrics.json\` — normalized quality evidence;
- \`stdout.log\` — native process stdout;
- \`stderr.log\` — native process stderr;
- \`run-receipt.json\` — source/profile/command/stem-format/metric summary and authority boundaries.

The returned artifact manifest records SHA-256, byte count, and evidence class for all four stems plus the metrics, logs, and run receipt.

## Output contract

A completed invocation returns the standard AIOS execution receipt plus:

- workflow: \`AUDIO_STEM_SECTION_ANALYSIS\`;
- engine: \`demucs\`;
- evidence class: \`MODEL_ESTIMATE\`;
- frozen profile ID;
- elapsed execution time;
- exact command argv;
- four artifact entries: drums, bass, other, vocals;
- SHA-256, byte count, and parsed WAV-format facts for each stem;
- normalized quality metrics;
- evidence-file pointers;
- artifact manifest with stem/evidence fingerprints;
- \`runtime_admission: false\`;
- \`pilot_authorized: false\`;
- \`authority_transfer: false\`.

The adapter uses an isolated staging directory and only promotes the complete four-stem set after output validation and metrics evidence generation. Existing destination directories are rejected rather than overwritten.

## Authority boundary

A successful separation, CI run, or same-track pilot produces evidence only. It does not grant runtime admission, pilot authorization, merge authority, or any broader AIOS authority.
