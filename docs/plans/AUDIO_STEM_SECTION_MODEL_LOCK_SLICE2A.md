# AUDIO_STEM_SECTION_ANALYSIS, Slice 2A Model and Profile Lock

Status: `PROFILE_LOCKED / RESOURCE ENVELOPE MEASURED / RUNTIME IMPLEMENTATION REVIEW REQUIRED / NO RUNTIME ADMISSION`

Scope: `udio-algorithms`

Profile: `slice2-stem-section-v0.1`

Tool identity: `audio.stem_section_analyze`

Authority transfer: `false`

## Purpose

Lock one reproducible four-stem CPU reference profile before executable Slice 2 stem and section analysis is implemented. This concern covers dependency identity, controlled acquisition, checksum verification, deterministic synthetic benchmarking, profile freezing, and static runtime-surface review.

It does not admit the tool into the registry, enable model downloads during analysis, authorize a real-track pilot, or merge the pull request.

## Selected baseline

- Package: `openunmix==1.3.0`
- Artifact: `openunmix-1.3.0-py3-none-any.whl`
- Artifact SHA-256: `e893ae22c5b8001a6107022499c2587b70d5c2e4777cc7c9ed6272b68a69534e`
- Artifact byte size: `40047`
- Source repository: `sigsep/open-unmix-pytorch`
- Release-code commit: `822ed57be7728ea42fca933305747251c7293d52`
- Model: `umxhq`
- Model record: `10.5281/zenodo.3370489`
- Targets: `vocals`, `drums`, `bass`, `other`
- Execution class: `CPU_REFERENCE`
- Input contract: stereo, 44,100 Hz
- Inference: CPU, one thread, residual disabled, one Wiener iteration, 300-frame Wiener window, Torch filterbank

## Controlled acquisition boundary

```text
approved HTTPS allowlist
→ quarantine-only download
→ original/final URL and redirect receipt
→ provider metadata capture
→ provider checksum verification
→ local SHA-256 and exact byte-size calculation
→ sealed transfer inventory
→ offline benchmark and verification
```

Only `pypi.org`, `files.pythonhosted.org`, `zenodo.org`, and `www.zenodo.org` are allowed during the dependency-fetch phase. Analysis remains offline. Missing, changed, redirected-to-unapproved-host, checksum-mismatched, or size-mismatched dependencies fail closed.

The successful controlled fetch was GitHub Actions run `30972750597`, job `92200410166`, on head `235ebb1c1249e5e61731ca32b81945d2810fdd3e`. Its transfer artifact was `8917163165`, sealed as `sha256:972de803d5f73f6c81fe88d763d2e0d4a48fc0eb4a01df2f536366ccb3512be6`.

## Locked weights

| Target | File | Provider MD5 | Local SHA-256 | Bytes |
| --- | --- | --- | --- | ---: |
| vocals | `vocals-b62c91ce.pth` | `d918985fad0fedf6d9ce89e279aa7218` | `b62c91cedbc7a066f1778ead5b5cecb377aa3a46a31af1cce7c5c8769339d083` | 35637796 |
| drums | `drums-9619578f.pth` | `cebf76e196e73e85d247f462c31e36fc` | `9619578f885c54737cb0234f9f9a4a679ee4f31438fd77fd1dbe02bb16c2da0a` | 35637796 |
| bass | `bass-8d85a5bd.pth` | `8cc37d31903fe48306468ee968f4b1b6` | `8d85a5bd3f996a8867fca0e8442e077e5a3f5ec747a6112742452a8f347b39c8` | 35637796 |
| other | `other-b52fbbf7.pth` | `8637606623ed7c74986789c3b1f94bc6` | `b52fbbf76479e752bd72e02304c602ac7802aa5bfbfb9cd12054b2695d5093ab` | 35637796 |

The files are locked as profile dependencies but are not admitted to a durable runtime cache by this pull request.

## Weight compatibility correction

The released UMXHQ state dictionaries contain three legacy compatibility keys not present in the current `OpenUnmix` module state:

- `sample_rate`
- `stft.window`
- `transform.0.window`

The benchmark loader now requires that exact set, verifies `sample_rate == 44100`, rejects missing model keys or any additional unexpected keys, filters only the known legacy compatibility entries, and then performs a strict model-state load. This mirrors the official loader's compatibility behavior without silently accepting arbitrary state-dict drift.

## Pretrained CPU resource measurement

Run classification: `PRETRAINED_SYNTHETIC_CPU_RESOURCE_BENCHMARK`

Fixture: deterministic five-second stereo multitone signal, generated locally, no copyrighted source.

Environment:

- Python `3.13.5`
- Open-Unmix `1.3.0`
- PyTorch `2.10.0+cpu`
- Torchaudio `2.10.0+cpu`
- NumPy `2.3.5`
- psutil `7.2.2`
- CPU threads `1`

Observed results:

- Model load: `2.797457 s`
- First inference: `1.493839 s`
- Second inference: `0.829990 s`
- Output shape: `(1, 4, 2, 220500)`
- Finite values: pass
- Same-context rerun: bit-identical
- Maximum rerun absolute difference: `0.0`
- Reconstruction residual RMS: `0.000414302630815655`
- Peak RSS: `796618752` bytes
- Quarantine bytes: `142615815`
- Benchmark artifact bytes: `8820280`
- Combined bytes: `151436095`

These measurements are a bounded synthetic CPU reference, not a full-track extrapolation or separation-quality claim.

## Frozen profile

Algorithm: `sha256-canonical-json-v1`

Checksum: `26ac1b86891a8dd7775a3b25bdb7f4b00d9ab284c7575815ce43c5f14e19680f`

The committed frozen profile binds package artifact, four weights, environment, inference parameters, and deterministic fixture. It is injected into the model-lock manifest, but not into the executable registry or runtime.

## Runtime implementation review

Run classification: `STATIC_RUNTIME_ADMISSION_SURFACE_REVIEW`

Reviewed surfaces:

- `registry/tools.v0.1.json`
- `policies/execution-policy.v0.1.json`
- `src/aios_tools/tools.py`
- `src/aios_tools/runner.py`
- contract bindings

Result: `audio.stem_section_analyze` is not registered, not allowed by policy, has no shared handler, and has no admitted contract binding. The correct decision is `SEPARATE_BOUNDED_RUNTIME_IMPLEMENTATION_PR_REQUIRED`.

Runtime admission remains `false`. Pilot authorization remains `false`.

## Evidence files

- `docs/evidence/AUDIO_STEM_SECTION_MODEL_LOCK_SLICE2A.json`
- `docs/evidence/AUDIO_STEM_SECTION_DEPENDENCY_FETCH_SLICE2A.json`
- `docs/evidence/AUDIO_STEM_SECTION_RESOURCE_ENVELOPE_SLICE2A.json`
- `docs/evidence/AUDIO_STEM_SECTION_FROZEN_PROFILE_SLICE2A.json`
- `docs/evidence/AUDIO_STEM_SECTION_RUNTIME_REVIEW_SLICE2A.json`

## Completed gates

- [x] Select UMXHQ as the primary four-stem CPU reference baseline.
- [x] Recheck package and weight-record licensing metadata during controlled fetch.
- [x] Pin the package wheel SHA-256 and exact byte size.
- [x] Fetch dependencies into quarantine through an explicit host allowlist.
- [x] Record original URL, final URL, redirect chain, provider metadata, and transfer artifact provenance.
- [x] Verify all four provider MD5 values.
- [x] Calculate all four local SHA-256 values and exact byte sizes.
- [x] Verify released weight compatibility and strict model-state loading.
- [x] Measure a pretrained synthetic CPU resource envelope.
- [x] Rerun inference in the same context and verify bit-identical output.
- [x] Freeze and verify the canonical profile checksum.
- [x] Review runtime admission surfaces.
- [x] Keep authority transfer disabled.

## Remaining gates

- [ ] Human review of PR #26.
- [ ] Separate bounded runtime implementation concern.
- [ ] Add input and result contracts.
- [ ] Add registry and policy admission.
- [ ] Add shared handler and CLI/MCP adapter coverage.
- [ ] Add cancellation, timeout, rollback, path-boundary, and receipt tests.
- [ ] Approve a durable local dependency-cache promotion mechanism.
- [ ] Run a licensed or user-supplied pilot only after runtime admission.

## Authority split

- Notion: architecture, governance, workflow status, and promotion authority.
- Google Drive: profile, ledger, dependency receipts, resource measurements, and artifacts.
- GitHub: executable implementation and version facts.
- Model files: dependencies only, never authority sources.

Successful checks remain evidence with `authority_transfer=false`.
