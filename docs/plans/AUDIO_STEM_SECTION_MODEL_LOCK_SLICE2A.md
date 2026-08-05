# AUDIO_STEM_SECTION_ANALYSIS — Slice 2A Model and Profile Lock

Status: `DECISION_CANDIDATE / MODEL_REVIEW_IN_PROGRESS / NO_RUNTIME_ADMISSION`

Parent plan: [`AUDIO_STEM_SECTION_ANALYSIS_SLICE2.md`](AUDIO_STEM_SECTION_ANALYSIS_SLICE2.md)

Issue: [#25](https://github.com/neohack2023/AIOS-Tools/issues/25)

Notion candidate: https://app.notion.com/p/3b343bd4ae4a81989575f3e2c80fe388

Drive dossier: https://docs.google.com/document/d/1v2gfE-JFbDZPSN7pdfIZIx7jqOWtKzDuJiKTjHRG864/edit

Drive ledger: https://docs.google.com/spreadsheets/d/12-Li4xI264lYL8f93MVh8Qs03xMpvT6ERVvenk0s2PM/edit

## 1. Purpose

Resolve the model-selection and inference-profile gate in the merged Slice 2 plan before contracts, registry admission, policy admission, executable code, or pilot execution are allowed.

This change documents a candidate. It does not install dependencies, fetch weights, execute separation, or alter runtime behavior.

## 2. Provisional baseline

- package: `openunmix==1.3.0`
- source repository: `sigsep/open-unmix-pytorch`
- release-code commit: `822ed57be7728ea42fca933305747251c7293d52`
- model ID: `umxhq`
- model record: Zenodo `3370489`, version `1.0.1`
- taxonomy: `vocals`, `drums`, `bass`, `other`
- execution class: `CPU_REFERENCE`
- profile ID: `slice2-stem-section-v0.1`

The official loader describes a stereo, 44.1 kHz Open-Unmix UMXHQ separator built from per-target three-layer bidirectional LSTM magnitude-mask models plus multichannel Wiener filtering.

Observed loader facts:

- `n_fft=4096`
- `n_hop=1024`
- `hidden_size=512`
- modeled bandwidth `16000 Hz`
- target set `vocals`, `drums`, `bass`, `other`

## 3. Proposed inference profile

```json
{
  "profile_id": "slice2-stem-section-v0.1",
  "model": "openunmix:umxhq",
  "package": "openunmix==1.3.0",
  "execution_class": "CPU_REFERENCE",
  "sample_rate_hz": 44100,
  "channels": 2,
  "targets": ["vocals", "drums", "bass", "other"],
  "device": "cpu",
  "residual": false,
  "niter": 1,
  "wiener_win_len": 300,
  "filterbank": "torch",
  "output_encoding": "WAV_FLOAT32",
  "network_during_analysis": false,
  "overwrite_source_or_slice1": false,
  "authority_transfer": false
}
```

The workflow computes its own reconstruction residual after all four estimated stems are frozen. The model's residual option therefore remains disabled in the baseline profile.

## 4. Weight candidates

| Target | File | Provider MD5 | Expected size |
|---|---|---|---|
| bass | `bass-8d85a5bd.pth` | `8cc37d31903fe48306468ee968f4b1b6` | about 35.6 MB |
| drums | `drums-9619578f.pth` | `cebf76e196e73e85d247f462c31e36fc` | about 35.6 MB |
| other | `other-b52fbbf7.pth` | `8637606623ed7c74986789c3b1f94bc6` | about 35.6 MB |
| vocals | `vocals-b62c91ce.pth` | `d918985fad0fedf6d9ce89e279aa7218` | about 35.6 MB |

Provider MD5 values are discovery evidence only. They do not satisfy the workflow checksum requirement.

Every admitted weight requires a locally computed SHA-256 and exact byte size from the controlled dependency-fetch phase.

## 5. Dependency-fetch boundary

Model acquisition and analysis execution are separate concerns.

The dependency-fetch phase must:

1. use an approved URL allowlist;
2. download into quarantine;
3. record the final URL and redirect chain;
4. verify the provider checksum where supplied;
5. compute local SHA-256 and exact byte size;
6. freeze a manifest before the files enter the admitted model cache;
7. never replace an admitted weight silently.

The admitted analysis path must run offline and fail with `MODEL_UNAVAILABLE` or `MODEL_WEIGHT_CHECKSUM_MISMATCH`. It must not download weights.

## 6. Selection rationale

Open-Unmix UMXHQ fits the baseline concern because:

- its output taxonomy exactly matches the Slice 2 contract;
- its package is MIT licensed;
- the repository is not archived;
- the model URLs and architecture are inspectable;
- CPU execution is supported;
- it is explicitly positioned as a reference implementation.

`umxl` is excluded from the baseline because the official project restricts its weights to non-commercial use.

Demucs remains a possible comparator under a separate future profile. It is not admitted here.

## 7. Determinism candidate

The CPU reference profile should record and pin:

- Python, FFmpeg, Open-Unmix, PyTorch, Torchaudio, NumPy, OS, and architecture versions;
- thread counts;
- random seeds;
- deterministic-algorithm settings;
- exact decoded/resampled input checksum;
- exact profile checksum;
- output artifact checksums.

Same-context bit identity is a validation target, not a claim. Tolerances must be derived from rerun evidence.

## 8. Remaining blockers

No implementation branch may add runtime code until all are resolved:

- [ ] explicit rights/license review for UMXHQ weights;
- [ ] approved Open-Unmix UMXHQ baseline decision;
- [ ] pinned PyTorch and Torchaudio versions;
- [ ] pinned package wheel or source artifact checksum;
- [ ] controlled fetch manifest with SHA-256 for all four weights;
- [ ] CPU resource-envelope evidence from a synthetic or properly licensed fixture;
- [ ] approved inference parameters;
- [ ] frozen profile JSON and checksum;
- [ ] human approval.

## 9. Implementation handoff after approval

The next bounded implementation concern may add:

- input and result contracts;
- offline model and profile manifests;
- dependency verification before model load;
- one shared implementation path for core, CLI, and MCP;
- registry and policy admission for `audio.stem_section_analyze`;
- synthetic fixtures and fail-closed tests;
- no copyrighted pilot audio in the repository;
- no pilot execution before implementation review.

## 10. Governance

Notion owns architecture, workflow status, and promotion.

Google Drive owns the profile, ledger, manifests, artifacts, and receipts.

GitHub owns executable implementation and version facts.

The model remains a dependency, not an authority source.

Every result must retain `authority_transfer: false`.
