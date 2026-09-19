# Blind Section Inference Plan — 2026-09-18

## Objective

Define a separate, deterministic blind section-inference capability that consumes frozen native Demucs evidence without modifying or extending stem-separation behavior.

This plan implements issue #66 as a planning artifact only.

## Base

- Repository: `neohack2023/AIOS-Tools`
- Base branch: `main`
- Base SHA: `e51d7f81d27923ac1121349229fd9a1813b21bde`
- Planning branch: `agent/blind-section-plan`

## Authority boundary

- GitHub owns live implementation, contracts, tests, registry, and policy facts.
- Drive remains the durable external knowledge authority where objects are `DRIVE_CURRENT` / `DRIVE_VERIFIED`.
- This plan does not authorize implementation, registry admission, runtime admission, pilot execution, or authority transfer.

`PLAN != AUTHORIZATION`

## Current upstream evidence

The current native Demucs path already freezes:

- original source identity and SHA-256;
- exact pinned profile identity;
- four stem identities and hashes;
- parsed WAV-format facts;
- normalized 44.1 kHz metrics;
- one-second RMS and peak activity windows for drums, bass, other, vocals;
- run receipt and artifact manifest;
- `authority_transfer=false`.

Blind section inference should consume those frozen artifacts rather than reopening model inference.

## Proposed capability boundary

Proposed new tool identity:

`audio.section.infer_blind`

Do not extend `audio.demucs.separate`.

### Input

Minimum required input:

- completed native Demucs run receipt;
- source SHA-256 and source duration/sample count from that receipt/evidence;
- frozen `analysis/stem-metrics.json`;
- expected native profile/run identity;
- optional output root for section evidence.

Rejected input classes during the blind stage:

- lyrics;
- prompts;
- genre labels;
- persona labels;
- claimed verse/hook/chorus/bridge/outro labels;
- human section annotations used as inference features.

Ground-truth labels may be used only in an offline evaluation fixture and must never enter the blind inference request.

### Output

- neutral ordered boundaries;
- neutral section IDs `S01`, `S02`, ...;
- start/end sample and second for each inferred section;
- raw boundary novelty score;
- threshold/profile facts;
- algorithm version;
- source/run/profile identities;
- evidence class;
- structured receipt;
- artifact manifest;
- `authority_transfer=false`.

No semantic section labels are produced.

## Deterministic algorithm candidate

This is the initial algorithm to evaluate, not yet a frozen runtime profile.

### Stage 1 — validate frozen evidence

Fail closed if:

- the Demucs run is not `COMPLETE`;
- source identity is missing or inconsistent;
- stem activity is missing for any expected stem;
- frame ordering is not strictly ascending;
- frame sample intervals overlap, regress, or disagree across stems;
- sample rate/channels/sample count disagree with the run receipt;
- any RMS/peak value is non-finite or negative;
- authority-transfer evidence is not exactly false.

### Stage 2 — build per-frame feature vectors

For each one-second activity frame, construct an 8-dimensional vector:

- drums RMS;
- drums peak;
- bass RMS;
- bass peak;
- other RMS;
- other peak;
- vocals RMS;
- vocals peak.

Apply a deterministic log transform:

`x' = log10(max(x, 1e-12))`

Normalize each feature independently across the track using median and median absolute deviation (MAD).

When MAD is zero, use scale `1.0` for that feature rather than dividing by zero.

### Stage 3 — boundary novelty

For each admissible frame boundary:

1. form a fixed-width left context window;
2. form a same-width right context window;
3. compute the mean normalized feature vector for each side;
4. compute Euclidean distance between the two means;
5. divide by `sqrt(feature_count)` so dimensionality remains explicit.

Initial evaluation profile:

- frame size: inherited 1 second from frozen metrics;
- left context: 3 frames;
- right context: 3 frames;
- edge candidates lacking full context: excluded.

No random state is permitted.

### Stage 4 — candidate extraction

Candidate boundaries must satisfy all of:

- local maximum in the novelty series;
- novelty above a robust track-derived threshold;
- minimum temporal distance from a stronger accepted boundary.

Proposed threshold form:

`median(novelty) + K * MAD(novelty)`

`K` is **not yet frozen**.

Proposed initial evaluation range:

- `K = 1.5, 2.0, 2.5, 3.0`
- minimum boundary spacing = `6, 8, 10` seconds.

These values are evaluation parameters only. The implementation profile must freeze one choice only after fixture evidence.

### Stage 5 — construct neutral sections

Always include:

- source start as section start;
- source end as final section end.

Accepted boundaries split the timeline into `S01`, `S02`, ... in ascending order.

Boundary positions are expressed in both seconds and samples using the frozen normalized sample rate.

## Why this first algorithm

The first implementation should depend only on evidence already emitted by the native adapter.

It therefore avoids:

- a second ML model;
- spectral re-decoding;
- prompt leakage;
- semantic labels;
- new network/model dependencies;
- separator/runtime coupling.

If evaluation shows that one-second stem activity is insufficient, that failure becomes evidence for a later plan rather than a reason to silently widen this one.

## Required contracts

Implementation, if later authorized, should add as one bounded unit:

- request schema;
- result schema;
- section-evidence schema or clearly versioned result structure;
- deterministic profile document;
- shared-core implementation;
- registry entry;
- execution-policy admission;
- CLI and MCP parity;
- tests;
- workflow documentation.

## Test obligations

### Contract and provenance

- reject missing/incomplete Demucs receipt;
- reject source-hash mismatch;
- reject profile/run mismatch;
- reject missing stem activity;
- reject `authority_transfer != false`.

### Blind-stage guards

- reject lyric/prompt/genre/persona/claimed-section fields;
- prove evaluation annotations are fixture-only and not accepted by runtime input.

### Numerical determinism

- identical input JSON produces identical section JSON byte-for-byte after canonical serialization;
- zero-MAD features do not create NaN/Inf;
- non-finite metrics fail closed;
- frame-order mismatch fails closed;
- boundary ordering is strictly monotonic;
- minimum-spacing rule is deterministic.

### Synthetic fixtures

At minimum:

1. no-change track -> no interior boundaries;
2. single abrupt activity transition -> one boundary near the known transition;
3. two well-separated transitions -> two ordered boundaries;
4. two close transitions -> stronger boundary wins spacing conflict;
5. gradual drift -> does not create a burst of false adjacent boundaries;
6. silent stem(s) -> zero-MAD fallback remains deterministic;
7. asymmetric stem change -> still detectable without semantic interpretation.

### Real-data evaluation

Use at least one previously governed track whose source identity is already known.

Real-data evaluation is quality evidence only. It must not create semantic truth labels automatically.

## Acceptance profile freeze

Before implementation is considered complete, freeze:

- algorithm version;
- feature list/order;
- log epsilon;
- context width;
- threshold coefficient `K`;
- minimum boundary spacing;
- tie-breaking rule;
- serialization order;
- evidence classes.

Profile freeze requires fixture evidence, not intuition alone.

## Proposed evidence classes

- input stem activity: `QUALITY_PROXY`;
- raw novelty curve: `DERIVED_MEASUREMENT`;
- inferred boundary: `MODEL_FREE_INFERENCE` or repository-standard equivalent if one already exists;
- human/evaluation labels: `REFERENCE_ANNOTATION`, fixture-only;
- run receipt: `EXECUTION_RECEIPT`.

If the repository has no accepted evidence class for deterministic inference, implementation must stop and resolve that contract question rather than inventing one silently.

## Slices

### Slice A — contracts + deterministic core

- input/result contracts;
- provenance validation;
- blind-stage guard;
- feature extraction;
- novelty computation;
- candidate extraction;
- synthetic tests.

No registry/policy admission yet if repository law requires contracts/core review first.

### Slice B — governed tool integration

- registry/policy entry;
- CLI/MCP parity;
- output-root handling;
- receipt + manifest;
- exact-head validation.

### Slice C — evaluation/profile freeze

- evaluate parameter grid on synthetic fixtures;
- run bounded real-data evaluation;
- choose one frozen profile;
- update tests to assert frozen behavior;
- human review before any pilot/runtime-admission decision.

## Non-goals

- no semantic labels;
- no lyric transcription;
- no prompt-aware inference;
- no speaker/persona detection;
- no new ML model;
- no separator modification;
- no model download;
- no external network effects;
- no automatic canon or MASON promotion;
- no runtime admission;
- no global pilot authorization;
- no authority transfer.

## Rollback

Because planning alone changes no runtime behavior, rollback is simply closing the planning PR unmerged.

For any future implementation, rollback must be a normal Git revert with no mutation of historical evidence receipts.

## Unresolved decisions

1. Accepted evidence-class name for deterministic inferred boundaries.
2. Final `K` threshold coefficient.
3. Final minimum boundary spacing.
4. Whether one-second activity frames are sufficient for the intended temporal resolution.
5. Whether source-mix features are needed at all. They are excluded from the first implementation candidate unless fixture evidence proves necessary.

## Promotion gate

No implementation begins from this plan merely because the planning PR merges.

Required next state:

`PLAN_ACCEPTED / IMPLEMENTATION_SEPARATELY_AUTHORIZED`

Until then:

`runtime_admission=false`
`pilot_authorized=false`
`authority_transfer=false`
