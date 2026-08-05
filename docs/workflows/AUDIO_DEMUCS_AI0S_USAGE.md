# AIOS Native Demucs Workflow

## Status

Implementation candidate. The full-track `L04D-B34R1NG_SP4RK` pilot completed successfully with the frozen `htdemucs` profile. Runtime admission remains false until PR review and CI complete.

## Registered tool

`audio.demucs.separate`

- mode: `WRITE`
- reversibility: `PARTIAL`
- blast radius: `LOCAL_FILES`
- external network effects: disabled
- authority transfer: false
- approval: required before handler invocation

## Frozen runtime

- Demucs: `4.1.0`
- model: `htdemucs`
- device: CPU
- jobs: `1`
- segment: `7` seconds
- overlap: `0.10`
- shifts: `0`
- output: float32 WAV
- profile: `profiles/audio/demucs-htdemucs-native-cpu-v0.1.json`

## Request file

```json
{
  "source_path": "/absolute/path/to/source.wav",
  "output_dir": "/absolute/path/to/run-output",
  "profile_path": "/absolute/path/to/AIOS-Tools/profiles/audio/demucs-htdemucs-native-cpu-v0.1.json"
}
```

## Approval file

```json
{
  "approval": {
    "approved": true,
    "approved_by": "human-operator-id",
    "tool": "audio.demucs.separate",
    "scope": "udio-algorithms"
  }
}
```

## Invocation

```bash
aios-tools invoke audio.demucs.separate \
  --mode WRITE \
  --scope udio-algorithms \
  --authority-context @approval.json \
  --input @request.json
```

Without a matching approval object, the runner returns `APPROVAL_REQUIRED` before the Demucs handler starts.

## Output contract

A completed invocation returns the standard AIOS execution receipt plus:

- workflow: `AUDIO_STEM_SECTION_ANALYSIS`
- engine: `demucs`
- evidence class: `MODEL_ESTIMATE`
- frozen profile ID
- elapsed execution time
- exact command argv
- four artifact entries: drums, bass, other, vocals
- SHA-256 and byte count for each stem
- runtime admission: false
- authority transfer: false

The adapter uses an isolated staging directory and only promotes the complete four-stem set after validation. Existing destination directories are rejected rather than overwritten.
