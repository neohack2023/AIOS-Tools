from __future__ import annotations

import argparse
import importlib.metadata
import json
import math
import os
import platform
import shutil
import struct
import sys
import threading
import time
from pathlib import Path
from typing import Any

from audio_model_lock_common import *

def build_fixture(duration_seconds: float, sample_rate: int):
    import torch

    sample_count = int(round(duration_seconds * sample_rate))
    time_axis = torch.arange(sample_count, dtype=torch.float32) / sample_rate
    left = (
        0.20 * torch.sin(2 * math.pi * 110.0 * time_axis)
        + 0.13 * torch.sin(2 * math.pi * 220.0 * time_axis + 0.2)
        + 0.08 * torch.sin(2 * math.pi * 440.0 * time_axis + 0.4)
    )
    right = (
        0.18 * torch.sin(2 * math.pi * 110.0 * time_axis + 0.1)
        + 0.11 * torch.sin(2 * math.pi * 330.0 * time_axis + 0.3)
        + 0.07 * torch.sin(2 * math.pi * 880.0 * time_axis + 0.5)
    )
    return torch.stack([left, right], dim=0).unsqueeze(0).contiguous()


def _load_state_dict(path: Path):
    import torch

    try:
        payload = torch.load(path, map_location="cpu", weights_only=True)
    except TypeError:
        payload = torch.load(path, map_location="cpu")
    if isinstance(payload, dict) and "state_dict" in payload and isinstance(payload["state_dict"], dict):
        return payload["state_dict"]
    if not isinstance(payload, dict):
        raise DependencyLockError(f"unexpected weight payload type: {path.name}")
    return payload


def _installed_version(distribution: str) -> str:
    try:
        return importlib.metadata.version(distribution)
    except importlib.metadata.PackageNotFoundError as exc:
        raise DependencyLockError(f"required distribution is not installed: {distribution}") from exc


def _artifact_record(path: Path, kind: str) -> dict[str, Any]:
    hashes = hash_file(path)
    return {"kind": kind, "filename": path.name, "sha256": hashes["sha256"], "byte_size": hashes["byte_size"]}


def run_benchmark(args: argparse.Namespace) -> int:
    fetch_receipt = load_json(args.fetch_receipt)
    base = load_json(args.manifest)
    _validate_base_manifest(base)
    if fetch_receipt.get("status") != "DEPENDENCIES_QUARANTINED_VERIFIED":
        raise DependencyLockError("dependency fetch receipt is not admitted")
    if fetch_receipt.get("authority_transfer") is not False:
        raise DependencyLockError("dependency receipt authority_transfer must be false")

    quarantine = args.quarantine.resolve()
    package_path = quarantine / "package" / fetch_receipt["package_artifact"]["filename"]
    package_hash = hash_file(package_path)
    if package_hash["sha256"] != fetch_receipt["package_artifact"]["local_sha256"]:
        raise DependencyLockError("package artifact changed after quarantine verification")

    weights_dir = quarantine / "weights"
    weight_by_target = {item["target"]: item for item in fetch_receipt["weights"]}
    for target in EXPECTED_TARGETS:
        item = weight_by_target.get(target)
        if item is None:
            raise DependencyLockError(f"missing fetched weight receipt for {target}")
        actual = hash_file(weights_dir / item["filename"])
        if actual["sha256"] != item["sha256"] or actual["byte_size"] != item["byte_size"]:
            raise DependencyLockError(f"quarantined weight changed after verification: {target}")

    import numpy as np
    import openunmix
    import psutil
    import torch
    from openunmix.model import Separator

    torch.set_num_threads(args.thread_count)
    torch.set_num_interop_threads(1)
    torch.manual_seed(0)
    np.random.seed(0)
    torch.use_deterministic_algorithms(True)

    sampler = PeakMemorySampler()
    sampler.start()
    process = psutil.Process(os.getpid())
    baseline_rss = process.memory_info().rss

    load_start = time.perf_counter()
    target_models = openunmix.umxhq_spec(targets=EXPECTED_TARGETS, device="cpu", pretrained=False)
    legacy_compatibility_keys = {"sample_rate", "stft.window", "transform.0.window"}
    ignored_weight_keys: dict[str, list[str]] = {}
    for target in EXPECTED_TARGETS:
        state_dict = _load_state_dict(weights_dir / weight_by_target[target]["filename"])
        model_keys = set(target_models[target].state_dict())
        state_keys = set(state_dict)
        missing_from_weight = sorted(model_keys - state_keys)
        extra_in_weight = sorted(state_keys - model_keys)
        if missing_from_weight:
            raise DependencyLockError(
                f"state-dict missing model keys for {target}: {missing_from_weight}"
            )
        if set(extra_in_weight) != legacy_compatibility_keys:
            raise DependencyLockError(
                f"unexpected compatibility keys for {target}: {extra_in_weight}"
            )
        sample_rate_value = state_dict.get("sample_rate")
        if sample_rate_value is None or float(sample_rate_value) != 44100.0:
            raise DependencyLockError(f"weight sample_rate mismatch for {target}")
        filtered_state_dict = {key: value for key, value in state_dict.items() if key in model_keys}
        incompatible = target_models[target].load_state_dict(filtered_state_dict, strict=True)
        if incompatible.missing_keys or incompatible.unexpected_keys:
            raise DependencyLockError(
                f"state-dict mismatch for {target}: missing={incompatible.missing_keys}, unexpected={incompatible.unexpected_keys}"
            )
        ignored_weight_keys[target] = extra_in_weight
        target_models[target].eval()
    separator = Separator(
        target_models=target_models,
        niter=1,
        residual=False,
        n_fft=4096,
        n_hop=1024,
        nb_channels=2,
        sample_rate=44100.0,
        wiener_win_len=300,
        filterbank="torch",
    ).to("cpu")
    separator.eval()
    load_seconds = time.perf_counter() - load_start
    rss_after_load = process.memory_info().rss
    peak_rss_after_load = sampler.peak_rss

    fixture = build_fixture(args.fixture_seconds, 44100)
    bench_dir = args.bench_dir.resolve()
    if bench_dir.exists():
        shutil.rmtree(bench_dir)
    bench_dir.mkdir(parents=True, exist_ok=True)
    input_path = bench_dir / "synthetic-reference-input.wav"
    write_float32_wav(input_path, fixture, 44100)

    with torch.inference_mode():
        first_start = time.perf_counter()
        first = separator(fixture)
        first_seconds = time.perf_counter() - first_start
        second_start = time.perf_counter()
        second = separator(fixture)
        second_seconds = time.perf_counter() - second_start

    if list(first.shape) != [1, 4, 2, fixture.shape[-1]]:
        raise DependencyLockError(f"unexpected pretrained output shape: {tuple(first.shape)}")
    if not torch.isfinite(first).all().item() or not torch.isfinite(second).all().item():
        raise DependencyLockError("pretrained output contains non-finite values")
    bit_identical = torch.equal(first, second)
    max_abs_diff = float(torch.max(torch.abs(first - second)).item())
    reconstructed = first.sum(dim=1)
    residual = fixture - reconstructed
    reconstruction_rms = float(torch.sqrt(torch.mean(residual * residual)).item())

    artifacts = [_artifact_record(input_path, "synthetic_input")]
    for index, target in enumerate(EXPECTED_TARGETS):
        stem_path = bench_dir / f"{target}.wav"
        write_float32_wav(stem_path, first[:, index], 44100)
        artifacts.append(_artifact_record(stem_path, f"estimated_{target}"))

    sampler.stop()
    final_rss = process.memory_info().rss
    peak_rss = sampler.peak_rss
    quarantine_bytes = directory_size(quarantine)
    benchmark_artifact_bytes = directory_size(bench_dir)

    environment = {
        "python": platform.python_version(),
        "openunmix": _installed_version("openunmix"),
        "torch": torch.__version__,
        "torchaudio": _installed_version("torchaudio"),
        "numpy": np.__version__,
        "psutil": psutil.__version__,
        "os": platform.platform(),
        "machine": platform.machine(),
        "processor": platform.processor(),
        "cpu_count_logical": os.cpu_count(),
        "thread_count": args.thread_count,
    }
    profile = {
        "profile_id": PROFILE_ID,
        "profile_state": "FROZEN_NOT_RUNTIME_ADMITTED",
        "tool_identity": TOOL_IDENTITY,
        "package": {
            "filename": fetch_receipt["package_artifact"]["filename"],
            "sha256": fetch_receipt["package_artifact"]["local_sha256"],
            "byte_size": fetch_receipt["package_artifact"]["byte_size"],
        },
        "weights": [
            {
                "target": target,
                "filename": weight_by_target[target]["filename"],
                "sha256": weight_by_target[target]["sha256"],
                "byte_size": weight_by_target[target]["byte_size"],
            }
            for target in EXPECTED_TARGETS
        ],
        "environment": environment,
        "inference": {
            "execution_class": "CPU_REFERENCE",
            "sample_rate_hz": 44100,
            "channels": 2,
            "targets": EXPECTED_TARGETS,
            "device": "cpu",
            "thread_count": args.thread_count,
            "residual": False,
            "niter": 1,
            "wiener_win_len": 300,
            "filterbank": "torch",
            "output_encoding": "WAV_FLOAT32",
            "network_during_analysis": False,
            "authority_transfer": False,
        },
        "fixture": {
            "kind": "deterministic_synthetic_multitone_stereo",
            "duration_seconds": args.fixture_seconds,
            "input_sha256": artifacts[0]["sha256"],
            "copyrighted_source": False,
        },
    }
    profile_checksum = canonical_sha256(profile)
    frozen_profile = {**profile, "profile_checksum_algorithm": "sha256-canonical-json-v1", "profile_checksum": profile_checksum}
    write_json(args.profile_output, frozen_profile)

    receipt = {
        "schema_version": "0.1.0",
        "status": "PROFILE_FROZEN_RESOURCE_ENVELOPE_MEASURED",
        "run_classification": "PRETRAINED_SYNTHETIC_CPU_RESOURCE_BENCHMARK",
        "profile_id": PROFILE_ID,
        "tool_identity": TOOL_IDENTITY,
        "measured_at": utc_now(),
        "authority_transfer": False,
        "environment": environment,
        "fixture": frozen_profile["fixture"],
        "model_load": {
            "elapsed_seconds": round(load_seconds, 6),
            "baseline_rss_bytes": baseline_rss,
            "rss_after_load_bytes": rss_after_load,
            "peak_rss_after_load_bytes": peak_rss_after_load,
            "ignored_legacy_weight_keys": ignored_weight_keys,
        },
        "inference": {
            "first_elapsed_seconds": round(first_seconds, 6),
            "second_elapsed_seconds": round(second_seconds, 6),
            "output_shape": list(first.shape),
            "finite_values": True,
            "same_context_bit_identical": bit_identical,
            "same_context_max_abs_diff": max_abs_diff,
            "reconstruction_residual_rms": reconstruction_rms,
            "final_rss_bytes": final_rss,
            "peak_rss_bytes": peak_rss,
        },
        "disk": {
            "quarantine_bytes": quarantine_bytes,
            "benchmark_artifact_bytes": benchmark_artifact_bytes,
            "combined_bytes": quarantine_bytes + benchmark_artifact_bytes,
        },
        "artifacts": artifacts,
        "profile_checksum_algorithm": "sha256-canonical-json-v1",
        "profile_checksum": profile_checksum,
        "scope": "five-second deterministic synthetic CPU reference; no full-track extrapolation",
        "gates": {
            "package_artifact_locked": True,
            "all_weight_provider_checksums_verified": True,
            "all_weight_sha256_present": True,
            "resource_envelope_measured_with_pretrained_weights": True,
            "profile_checksum_frozen": True,
            "runtime_review_completed": False,
            "runtime_admission": False,
            "pilot_authorized": False,
        },
    }
    write_json(args.output, receipt)
    print("BENCHMARK_RECEIPT_JSON=" + json.dumps(receipt, sort_keys=True, separators=(",", ":")))
    return 0


