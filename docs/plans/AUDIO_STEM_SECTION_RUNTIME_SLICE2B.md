# AUDIO_STEM_SECTION_ANALYSIS — Slice 2B Runtime Implementation

Status: `IMPLEMENTATION_IN_PROGRESS / DRAFT_PR_REQUIRED / NO_RUNTIME_ADMISSION / NO_PILOT`

Issue: [#27](https://github.com/neohack2023/AIOS-Tools/issues/27)

Parent plan: [Slice 2](./AUDIO_STEM_SECTION_ANALYSIS_SLICE2.md)

Model/profile lock: [PR #26](https://github.com/neohack2023/AIOS-Tools/pull/26)

Branch: `agent/audio-stem-section-runtime`

Tool identity: `audio.stem_section_analyze`

Profile: `slice2-stem-section-v0.1`

Profile checksum: `26ac1b86891a8dd7775a3b25bdb7f4b00d9ab284c7575815ce43c5f14e19680f`

## Purpose

Convert the frozen Slice 2A model/profile lock into one bounded runtime capability that produces local evidence artifacts without network access, connector writes, source mutation, or authority transfer.

This concern does not authorize the `L04D-B34R1NG_SP4RK` pilot until the implementation PR is reviewed, all tests pass, and the runtime-admission gate is explicitly changed by human review.

## Frozen facts

- package: `openunmix==1.3.0`
- model: `umxhq`
- execution class: `CPU_REFERENCE`
- sample rate: `44100 Hz`
- channels: `2`
- targets: `vocals`, `drums`, `bass`, `other`
- residual from model: `false`
- Wiener iterations: `1`
- Wiener window length: `300`
- filterbank: `torch`
- analysis network: `false`
- authority transfer: `false`

Runtime code may not override these values through request fields.

## Implementation order

```text
contracts
→ dependency/profile verifier
→ bounded workspace and path policy
→ shared runtime stages
→ artifact manifest and receipts
→ CLI adapter
→ MCP adapter
→ registry and policy admission
→ synthetic tests
→ failure and rollback tests
→ human review
```

## Stage contract

1. **Request validation**
   - validate the tool request and audio-specific input schema;
   - require explicit scope and caller identity;
   - reject prompt, lyric, genre, persona, or claimed-section fields from blind-stage input.

2. **Source dependency verification**
   - require a completed Slice 1 receipt;
   - verify the source path exists and is a regular file;
   - verify the exact source SHA-256 before decode;
   - fail before model load on mismatch.

3. **Model/profile verification**
   - verify the canonical profile checksum;
   - verify package and four weight facts;
   - reject missing or mismatched dependencies;
   - prohibit network access during analysis.

4. **Bounded workspace**
   - resolve source, Slice 1 receipt, model cache, temporary root, and output root;
   - reject path traversal and symlink escapes;
   - reject overwrite of source, prior receipts, or existing output files;
   - write only inside a transaction-local temporary directory until final validation.

5. **Blind stem estimation**
   - decode to stereo float32 PCM at 44,100 Hz;
   - run the frozen UMXHQ CPU profile;
   - emit four estimated stems;
   - validate shape, duration, sample rate, channels, finite values, clipping, and checksums.

6. **Reconstruction and quality proxies**
   - calculate summed-stem reconstruction and residual;
   - calculate reconstruction RMS error and residual-to-mix energy ratio;
   - calculate per-stem activity timelines and overlap proxies;
   - preserve evidence classes as measured, model estimate, or quality proxy.

7. **Stem freeze boundary**
   - serialize and checksum stem evidence before section inference;
   - do not expose prompt-comparison data to blind stages.

8. **Blind section inference**
   - use the original mix, frozen Slice 1 features, and frozen stem activity;
   - emit neutral IDs only, such as `S01`, `S02`, and `S03`;
   - do not emit verse, chorus, hook, bridge, intro, outro, speaker, or persona labels.

9. **Artifact validation and promotion**
   - verify the complete required artifact set;
   - compute SHA-256 and exact byte size for every artifact;
   - atomically move the validated transaction directory into the approved output root;
   - rollback partial temporary artifacts on failure, cancellation, or timeout.

10. **Receipt**
    - record tool, registry, policy, profile, model, environment, source, Slice 1 dependency, stages, timings, local effects, artifact manifest, and errors;
    - retain `authority_transfer=false`.

## Contract files

The implementation PR must add:

- `contracts/audio-stem-section-input.v0.1.schema.json`
- `contracts/audio-stem-section-result.v0.1.schema.json`
- `contracts/audio-stem-section-artifact-manifest.v0.1.schema.json`

## Runtime surfaces

Expected implementation files:

- `src/aios_tools/audio/__init__.py`
- `src/aios_tools/audio/boundaries.py`
- `src/aios_tools/audio/dependencies.py`
- `src/aios_tools/audio/runtime.py`
- `src/aios_tools/audio/sections.py`
- `src/aios_tools/audio/wav.py`
- updates to `src/aios_tools/tools.py`
- updates to `src/aios_tools/mcp_server.py`
- updates to `registry/tools.v0.1.json`
- updates to `policies/execution-policy.v0.1.json`

The CLI continues to use the shared `invoke` path. The MCP adapter must call the same handler and may not duplicate analysis logic.

## Failure model

At minimum:

- `FAILED_SOURCE_DEPENDENCY`
- `SOURCE_CHECKSUM_MISMATCH`
- `SLICE1_RECEIPT_MISSING`
- `PROFILE_CHECKSUM_MISMATCH`
- `MODEL_UNAVAILABLE`
- `MODEL_WEIGHT_CHECKSUM_MISMATCH`
- `NETWORK_ACCESS_PROHIBITED`
- `PATH_BOUNDARY_VIOLATION`
- `OVERWRITE_PROHIBITED`
- `FAILED_DECODE`
- `SEPARATION_RUNTIME_ERROR`
- `INCOMPLETE_STEM_SET`
- `INVALID_STEM_SHAPE`
- `INVALID_STEM_VALUE`
- `STEM_DURATION_MISMATCH`
- `STEM_SAMPLE_RATE_MISMATCH`
- `STEM_CHANNEL_MISMATCH`
- `PROMPT_LEAK_INTO_BLIND_PASS`
- `SECTION_ANALYSIS_FAILED`
- `INCOMPLETE_ARTIFACT_SET`
- `CANCELLED`
- `TIMEOUT`
- `ROLLBACK_FAILED`

## Test gates

- request and result schema validation;
- missing or invalid Slice 1 receipt rejection;
- source checksum mismatch before model load;
- profile, package, and weight mismatch rejection;
- no-network analysis enforcement;
- prompt-leak guard;
- stage-order enforcement;
- invalid shape, channel, sample-rate, duration, NaN, and Inf rejection;
- path traversal and symlink escape rejection;
- source and prior-artifact overwrite rejection;
- cancellation and timeout rollback;
- required artifact completeness and checksum validation;
- deterministic synthetic fixture;
- CLI and MCP adapter parity;
- receipt preserves `authority_transfer=false`;
- CI never runs the user pilot.

## Admission boundary

Until the implementation PR is reviewed and merged:

```text
runtime_admission=false
pilot_authorized=false
authority_transfer=false
```

A passing test or merged PR remains implementation evidence. It does not promote output into canon or MASON.
