# AUDIO_STEM_SECTION_ANALYSIS - Slice 2A Model and Profile Lock

Status: `DECISION_CANDIDATE / BASELINE_SELECTED / NO_RUNTIME_ADMISSION`

Parent plan: [`AUDIO_STEM_SECTION_ANALYSIS_SLICE2.md`](AUDIO_STEM_SECTION_ANALYSIS_SLICE2.md)

Issue: [#25](https://github.com/neohack2023/AIOS-Tools/issues/25)

Notion decision candidate: https://app.notion.com/p/3b343bd4ae4a817087f2fb9f56936545

Parent Notion workflow: https://app.notion.com/p/3b343bd4ae4a81989575f3e2c80fe388

Drive dossier: https://docs.google.com/document/d/1v2gfE-JFbDZPSN7pdfIZIx7jqOWtKzDuJiKTjHRG864/edit

Drive ledger: https://docs.google.com/spreadsheets/d/12-Li4xI264lYL8f93MVh8Qs03xMpvT6ERVvenk0s2PM/edit

## 1. Purpose

Resolve the model-selection and inference-profile gate in the merged Slice 2 plan before contracts, registry admission, policy admission, executable code, or pilot execution are allowed.

This change locks a candidate baseline and records compatibility evidence. It does not fetch pretrained weights, execute separation with pretrained weights, alter the runtime registry, or authorize pilot execution.

## 2. Selected reference baseline

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

## 3. Pinned CPU reference environment

The first compatibility reference is pinned to the environment in which the model constructor and synthetic smoke test actually ran:

- Python `3.13.5`
- Open-Unmix `1.3.0`
- PyTorch `2.10.0+cpu`
- Torchaudio `2.10.0+cpu`
- NumPy `2.3.5`
- FFmpeg `7.1.3`
- device `cpu`
- thread count `1` for the recorded smoke test

This pin is an observed compatibility profile, not a claim that other versions are unsupported.

## 4. Candidate inference profile

```json
{
  "profile_id": "slice2-stem-section-v0.1",
  "model": "openunmix:umxhq",
  "package": "openunmix==1.3.0",
  "python": "3.13.5",
  "torch": "2.10.0+cpu",
  "torchaudio": "2.10.0+cpu",
  "numpy": "2.3.5",
  "ffmpeg": "7.1.3",
  "execution_class": "CPU_REFERENCE",
  "sample_rate_hz": 44100,
  "channels": 2,
  "targets": ["vocals", "drums", "bass", "other"],
  "device": "cpu",
  "thread_count": 1,
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

The workflow computes its own reconstruction residual after all four estimated stems are frozen. The model residual option therefore remains disabled in the baseline profile.

## 5. Verified compatibility smoke test

The following checks were executed in the pinned CPU environment:

```text
openunmix package version: 1.3.0
separator constructor: PASS
separator sample rate: 44100
separator targets: vocals, drums, bass, other
synthetic input: 1 second, stereo, 44100 Hz, float32 zeros
output shape: (1, 4, 2, 44100)
finite-value check: PASS
elapsed inference time: 0.215 seconds
```

The constructor used:

```python
umxhq(
    pretrained=False,
    device="cpu",
    residual=False,
    niter=1,
    wiener_win_len=300,
    filterbank="torch",
)
```

This smoke test verifies package import, model construction, tensor shape, taxonomy, and CPU execution compatibility. It does not verify pretrained weight integrity, separation quality, model licensing, or production resource use.

The installed Open-Unmix distribution `RECORD` file was present and had SHA-256:

`d1c41f55cd0f18ee171fbec76b6448b4f4d958058683b8aba6ba30227e7a6317`

This is an installed-environment fingerprint only. It is not a substitute for the required wheel or source-artifact checksum.

## 6. Rights and license review

- the Open-Unmix source package declares the MIT license;
- the Zenodo UMXHQ record is published as open software;
- DataCite/OpenAIRE metadata for record `3370489` reports MIT licensing;
- the admitted dependency manifest must preserve the record DOI, resolved license identifier, source URL, retrieval timestamp, and local checksums;
- Zenodo hosting does not transfer intellectual-property rights, so use remains subject to the deposited record license.

The UMXHQ weight rights review is provisionally satisfied for the model-lock decision. It must be rechecked and captured in the controlled dependency manifest when the exact files are fetched.

`umxl` remains excluded because the official project explicitly limits those weights to non-commercial use under CC BY-NC-SA 4.0.

## 7. Weight candidates

| Target | File | Provider MD5 | Expected size |
|---|---|---|---|
| bass | `bass-8d85a5bd.pth` | `8cc37d31903fe48306468ee968f4b1b6` | about 35.6 MB |
| drums | `drums-9619578f.pth` | `cebf76e196e73e85d247f462c31e36fc` | about 35.6 MB |
| other | `other-b52fbbf7.pth` | `8637606623ed7c74986789c3b1f94bc6` | about 35.6 MB |
| vocals | `vocals-b62c91ce.pth` | `d918985fad0fedf6d9ce89e279aa7218` | about 35.6 MB |

Provider MD5 values are discovery evidence only. They do not satisfy the workflow checksum requirement.

Every admitted weight requires a locally computed SHA-256 and exact byte size from the controlled dependency-fetch phase.

## 8. Dependency-fetch boundary

Model acquisition and analysis execution are separate concerns.

The dependency-fetch phase must:

1. use an approved URL allowlist;
2. download into quarantine;
3. record the original URL, final URL, and redirect chain;
4. verify the provider checksum where supplied;
5. compute local SHA-256 and exact byte size;
6. record the license evidence attached to the exact record;
7. freeze a manifest before the files enter the admitted model cache;
8. never replace an admitted weight silently.

The admitted analysis path must run offline and fail with `MODEL_UNAVAILABLE` or `MODEL_WEIGHT_CHECKSUM_MISMATCH`. It must not download weights.

## 9. Selection rationale

Open-Unmix UMXHQ fits the baseline concern because:

- its output taxonomy exactly matches the Slice 2 contract;
- its source package is MIT licensed;
- the UMXHQ record is represented as MIT licensed in repository metadata aggregators sourced from Zenodo and DataCite;
- the repository is not archived;
- the model URLs and architecture are inspectable;
- CPU execution is supported;
- it is explicitly positioned as a reference implementation;
- the pinned environment passed a local constructor and synthetic-inference smoke test.

Demucs remains a possible comparator under a separate future profile. It is not admitted here.

## 10. Determinism candidate

The CPU reference profile records and pins:

- Python, FFmpeg, Open-Unmix, PyTorch, Torchaudio, NumPy, OS, and architecture versions;
- thread counts;
- random seeds;
- deterministic-algorithm settings;
- exact decoded and resampled input checksum;
- exact profile checksum;
- output artifact checksums.

Same-context bit identity is a validation target, not a claim. Tolerances must be derived from rerun evidence.

## 11. Approval record

Human authorization to correct the plan, test compatibility, build the lock package, and verify the next implementation gate was given in the governing project conversation on `2026-08-05`.

That authorization approves Open-Unmix UMXHQ as the selected reference baseline and approves the recorded CPU inference settings for implementation planning. It does not waive checksum, artifact, review, or pilot gates.

## 12. Remaining blockers

Runtime implementation and pilot execution remain blocked until all are resolved:

- [x] explicit rights and license review for UMXHQ record metadata;
- [x] approved Open-Unmix UMXHQ baseline decision;
- [x] pinned Python, PyTorch, Torchaudio, Open-Unmix, NumPy, and FFmpeg versions;
- [x] approved CPU inference parameters;
- [x] synthetic CPU constructor and inference smoke test;
- [ ] pinned package wheel or source-artifact checksum;
- [ ] controlled fetch manifest with SHA-256 for all four weights;
- [ ] CPU resource-envelope evidence using the pretrained weights and a synthetic or properly licensed fixture;
- [ ] frozen profile JSON and profile checksum after weight hashes are inserted;
- [ ] implementation PR review.

## 13. Implementation handoff after dependency lock

The next bounded implementation concern may add:

- input and result contracts;
- offline model and profile manifests;
- dependency verification before model load;
- one shared implementation path for core, CLI, and MCP;
- registry and policy admission for `audio.stem_section_analyze`;
- synthetic fixtures and fail-closed tests;
- no copyrighted pilot audio in the repository;
- no pilot execution before implementation review.

## 14. Governance

Notion owns architecture, workflow status, and promotion.

Google Drive owns the profile, ledger, manifests, artifacts, and receipts.

GitHub owns executable implementation and version facts.

The model remains a dependency, not an authority source.

Every result must retain `authority_transfer: false`.
