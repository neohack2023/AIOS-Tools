# AUDIO_STEM_SECTION_ANALYSIS — Slice 2 Plan

Status: `PLAN_ONLY / IMPLEMENTATION_BLOCKED / NOT VALIDATED`

Issue: [#23](https://github.com/neohack2023/AIOS-Tools/issues/23)

Frozen base commit: `f35ac60b14c6e3d120410f56968f982ffd1d2dc3`

Proposed branch: `agent/audio-stem-section-slice2`

Proposed tool identity: `audio.stem_section_analyze`

Proposed profile: `slice2-stem-section-v0.1`

## 1. Purpose

Add one bounded, read-only audio-analysis capability that extends a checksum-verified Slice 1 baseline into:

1. model-estimated stem separation;
2. stem integrity, reconstruction, and residual quality proxies;
3. blind section-boundary candidates derived from the original mix and frozen stem activity;
4. structured artifacts and an execution receipt.

This document plans implementation. It does not admit the tool into the registry, select a separation model, execute a pilot, or change runtime behavior.

## 2. Governing sources

### Notion authority

Notion owns architecture, workflow status, governance, project-memory linkage, and promotion decisions.

- Slice 1 workflow candidate: https://app.notion.com/p/3b343bd4ae4a8145adc9d01098e3e07b
- Pilot track evidence: https://app.notion.com/p/3b243bd4ae4a81fcb12ee63f393d5d0d
- Slice 2 candidate: to be registered after this plan branch exists

### Google Drive control plane

Google Drive owns the reproducibility specification, profile rows, run ledger, generated artifacts, and receipts.

- Workflow folder: https://drive.google.com/drive/folders/1ocKMFegwIFASpHHOg67Nd8sMMV4D5laG
- Slice 2 specification: https://docs.google.com/document/d/1iG2w-fEY-HSsQQMQTDqaWKfNvKpWwAdB_d69Ad5RxZI/edit
- Slice 2 ledger: https://docs.google.com/spreadsheets/d/12-Li4xI264lYL8f93MVh8Qs03xMpvT6ERVvenk0s2PM/edit
- Slice 1 pilot run folder: https://drive.google.com/drive/folders/16FhSmbOha9SN0gAuIRzEjHGW08F2OjU5

### GitHub authority

This repository may own executable implementation, schemas, registry entries, policy facts, tests, and tool-version facts. It must not redefine the architecture or promote evidence into durable memory.

Every result must retain `authority_transfer: false`.

## 3. Pilot dependency

- Track ID: `L04D-B34R1NG_SP4RK`
- Completed Slice 1 run: `S1-20260805T015240Z-001`
- Source SHA-256: `3a1573821ed5ef792014bd5945cf4ca298c8f11b71a9088c65e207834ee5ae7e`
- Slice 1 blind tempo: `144.230769 BPM`
- Slice 1 whole-track key estimate: `F minor`

The proposed tool must fail before model loading when the source checksum or Slice 1 dependency does not match.

## 4. Planning blockers

Implementation and pilot execution remain blocked until all of the following are reviewed and pinned:

- source-separation package and exact version;
- model identifier and architecture name;
- model-weight SHA-256;
- output taxonomy;
- inference segment length, overlap, shift count, normalization, clipping behavior, and seed controls;
- supported device classes and minimum resource envelope;
- expected determinism or declared nondeterminism tolerances;
- license and redistribution implications for package, code, and model weights.

The initial taxonomy is proposed as `vocals`, `drums`, `bass`, and `other`, but it is not executable configuration until the selected model is pinned.

## 5. Execution contract

```text
request
  -> validate request schema
  -> resolve scope and authority context
  -> verify Slice 1 dependency and source checksum
  -> resolve admitted Slice 2 profile
  -> verify model identity and weight checksum
  -> run blind model-estimated stem separation
  -> validate stem shapes and files
  -> compute stem and reconstruction metrics
  -> freeze stem outputs
  -> run blind section-boundary analysis
  -> freeze section candidates
  -> optionally compare frozen candidates with supplied labels
  -> package structured result and receipt
```

The default posture remains read-only with respect to external systems. Writing artifacts to a caller-supplied local output directory is an explicit local execution effect and must be reported in the receipt.

## 6. Proposed request contract

A future `contracts/audio-stem-section-input.v0.1.schema.json` should require:

- `source_audio_path`
- `source_sha256`
- `slice1_run_id`
- `slice1_receipt_path` or a locally supplied receipt object
- `slice1_source_sha256`
- `profile_id`
- `output_directory`
- `scope_key`
- `requested_by`

The contract may optionally accept a prompt-comparison packet, but that packet must remain inaccessible to blind separation and blind section stages.

The request must not accept undocumented model overrides. Model selection belongs to the admitted profile.

## 7. Proposed result contract

A future `contracts/audio-stem-section-result.v0.1.schema.json` should separate:

- source dependency verification;
- environment and model facts;
- generated stem manifest;
- direct audio measurements;
- model estimates;
- quality proxies;
- blind section candidates;
- optional prompt comparison;
- artifact manifest;
- failure details;
- receipt metadata;
- `authority_transfer: false`.

Evidence classes must be explicit:

- `MEASURED`
- `MODEL_ESTIMATE`
- `QUALITY_PROXY`
- `PROMPT_COMPARISON`
- `HUMAN_REVIEW`

Human review is not produced by this tool. The result may reserve a separate field or external artifact reference for later review.

## 8. Stage boundaries

### Stage A: dependency and profile lock

Verify source and Slice 1 facts before model loading. Record profile and environment facts.

### Stage B: blind stem estimation

Inputs are limited to source audio and the pinned separation profile. Lyrics, genre, personas, prompts, and claimed section labels are excluded.

### Stage C: stem verification

For every generated stem, verify:

- file existence and SHA-256;
- finite sample values;
- duration tolerance;
- sample-rate and channel agreement;
- clipping state;
- declared encoding.

### Stage D: reconstruction and activity

Compute:

- summed-stem reconstruction;
- residual waveform;
- reconstruction RMS error;
- residual-to-mix energy ratio;
- mix versus reconstruction loudness difference;
- per-stem activity timelines;
- pairwise activity and spectral-overlap proxies;
- alignment and polarity warnings.

These are quality proxies, not ground-truth separation scores.

### Stage E: blind section inference

Use the original mix, frozen Slice 1 features, and frozen stem activity to produce neutral section identifiers such as `S01`, `S02`, and `S03`.

Each candidate should include boundaries, confidence, contributing evidence, mix and stem summaries, transition evidence, and adjacent-section distance.

Blind inference must not emit semantic labels such as verse, chorus, hook, bridge, breakdown, instrumental, intro, or outro.

### Stage F: optional prompt comparison

After blind outputs are serialized and frozen, compare claimed labels with candidate boundaries. Store comparison separately without replacing blind values.

## 9. Proposed implementation surfaces

Expected files for the implementation concern:

- `docs/plans/AUDIO_STEM_SECTION_ANALYSIS_SLICE2.md`
- `contracts/audio-stem-section-input.v0.1.schema.json`
- `contracts/audio-stem-section-result.v0.1.schema.json`
- `registry/tools.v0.1.json`
- `policies/execution-policy.v0.1.json`
- `src/aios_tools/tools.py` or a dedicated bounded audio module called by it
- `tests/test_audio_stem_section.py`
- optional deterministic fixtures that do not include copyrighted source audio
- validation documentation and receipt fixtures when required

The shared core, CLI, and MCP adapters must continue to call one implementation path. Adapters must not implement separate audio logic.

## 10. Registry proposal

The future registry entry should include:

- name: `audio.stem_section_analyze`
- version: `0.1.0`
- mode: `READ_ONLY`
- input schema reference
- result schema reference
- deterministic-status declaration
- execution-cost metadata
- local artifact effect declaration
- admitted profile IDs
- timeout and resource bounds

Registry admission is deferred until model and dependency facts are pinned.

## 11. Policy proposal

The future policy should require:

- explicit scope;
- source path inside an admitted local execution context;
- caller-supplied output directory;
- checksum-verified Slice 1 dependency;
- admitted profile only;
- no network access during execution unless a separately reviewed dependency-fetch phase exists;
- no connector writes;
- no overwrite of source audio or Slice 1 artifacts;
- no output outside the admitted artifact directory;
- failure on missing model metadata or weight mismatch;
- `authority_transfer: false`.

## 12. Failure model

The result contract and receipt should support at least:

- `FAILED_SOURCE_DEPENDENCY`
- `SOURCE_CHECKSUM_MISMATCH`
- `SLICE1_RECEIPT_MISSING`
- `MODEL_UNAVAILABLE`
- `MODEL_WEIGHT_CHECKSUM_MISMATCH`
- `UNSUPPORTED_AUDIO_FORMAT`
- `FAILED_DECODE`
- `SEPARATION_RUNTIME_ERROR`
- `STEM_DURATION_MISMATCH`
- `STEM_SAMPLE_RATE_MISMATCH`
- `STEM_CHANNEL_MISMATCH`
- `INVALID_STEM_VALUE`
- `EXCESSIVE_RECONSTRUCTION_ERROR`
- `INCOMPLETE_STEM_SET`
- `INCOMPLETE_ARTIFACT_SET`
- `SECTION_ANALYSIS_FAILED`
- `LOW_CONFIDENCE_SECTION_BOUNDARIES`
- `PROMPT_LEAK_INTO_BLIND_PASS`
- `NONDETERMINISTIC_PROFILE`

Thresholds that require empirical calibration must not be invented in this plan. They should be proposed from observed pilot and rerun evidence.

## 13. Mandatory artifact set

The future implementation should produce and checksum:

```text
source_dependency_manifest.json
separation_profile.json
environment.json
stem_manifest.json
stem_metrics.json
reconstruction_metrics.json
section_analysis.json
prompt_section_comparison.json  # optional
vocals.wav
drums.wav
bass.wav
other.wav
reconstructed_mix.wav
residual.wav
stem_activity.png
stem_spectrograms.png
reconstruction_error.png
section_novelty.png
section_stem_matrix.png
section_timeline.png
run_receipt.md
```

A missing required artifact prevents `COMPLETE` status.

## 14. Test plan

### Contract tests

- valid request passes schema validation;
- missing dependency fields fail;
- prompt-comparison data cannot enter blind-stage input structures;
- result requires evidence classes and authority-transfer flag.

### Dependency tests

- exact source and Slice 1 checksums pass;
- source mismatch fails before model load;
- missing or invalid Slice 1 receipt fails;
- unsupported profile fails closed.

### Model-fact tests

- missing model ID fails;
- missing model-weight checksum fails;
- mismatched weight checksum fails;
- model outputs with missing stems fail;
- NaN, Inf, invalid shape, sample-rate mismatch, channel mismatch, or duration mismatch fail.

### Stage-order tests

- stem results are serialized before section inference begins;
- blind sections are serialized before prompt comparison begins;
- prompt metadata is inaccessible to blind stage handlers.

### Artifact tests

- complete artifact manifest passes;
- missing required WAV, JSON, image, or receipt fails;
- artifact paths cannot escape the output directory;
- source and Slice 1 artifacts are never overwritten.

### Receipt tests

- receipt reports local artifact effects;
- receipt records tool, registry, policy, profile, model, environment, and checksums;
- receipt always contains `authority_transfer: false`.

## 15. Validation commands

After implementation exists, run the repository-required checks:

```bash
python -m pip install -e ".[dev]"
pytest
aios-tools list
aios-tools invoke system.health --input '{}'
aios-tools-mcp --help
```

Add focused audio tests and a bounded smoke invocation using a synthetic or properly licensed fixture. Do not report any command as passing until its output is captured.

## 16. Resource and security review

Before implementation, record:

- expected RAM and optional VRAM use;
- CPU and accelerator execution paths;
- model-load and inference timeout behavior;
- temporary-disk footprint;
- model license and package license;
- weight acquisition and verification process;
- whether any dependency attempts network access;
- cleanup and rollback behavior for partial artifact directories.

The implementation must not silently download weights during an admitted analysis run.

## 17. Rollback

The plan-only change can be reverted by closing the draft PR and deleting the branch after review. A later implementation rollback must remove the registry admission, policy admission, contracts, implementation, tests, and generated fixture changes as one coherent concern. Existing Drive and Notion evidence remains historical and is not deleted by a code rollback.

## 18. Promotion boundary

A merged implementation, passing tests, or completed pilot remains evidence. Workflow validation requires multiple tracks, a same-context rerun, a second execution context or device class, human review, declared tolerances derived from observed data, and explicit STONE → MASON authorization.

No automatic canon or architectural promotion is allowed.
