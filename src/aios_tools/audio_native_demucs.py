from __future__ import annotations

import hashlib
import importlib
import json
import math
import os
import shutil
import signal
import struct
import subprocess
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

EXPECTED_STEMS = ("drums", "bass", "other", "vocals")
EXPECTED_SAMPLE_RATE = 44100
EXPECTED_CHANNELS = 2
EXPECTED_FORMAT_CODE = 3
EXPECTED_BITS_PER_SAMPLE = 32
EXPECTED_BLOCK_ALIGN = 8
METRIC_FRAME_SAMPLES = EXPECTED_SAMPLE_RATE


class NativeDemucsError(RuntimeError):
    def __init__(self, code: str, message: str, *, details: dict[str, Any] | None = None) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.details = details or {}


@dataclass(frozen=True)
class NativeDemucsProfile:
    profile_id: str
    entrypoint: tuple[str, ...]
    model: str
    device: str
    jobs: int
    split: bool
    segment_seconds: float
    overlap: float
    shifts: int
    output_format: str
    float32: bool
    timeout_seconds: int
    source_sha256: str | None = None

    @classmethod
    def from_json(cls, path: Path) -> "NativeDemucsProfile":
        data = json.loads(path.read_text(encoding="utf-8"))
        return cls(
            profile_id=str(data["profile_id"]),
            entrypoint=tuple(data["entrypoint"]),
            model=str(data["model"]),
            device=str(data["device"]),
            jobs=int(data["jobs"]),
            split=bool(data["split"]),
            segment_seconds=float(data["segment_seconds"]),
            overlap=float(data["overlap"]),
            shifts=int(data["shifts"]),
            output_format=str(data["output_format"]),
            float32=bool(data["float32"]),
            timeout_seconds=int(data["timeout_seconds"]),
            source_sha256=data.get("source_sha256"),
        )

    def validate(self) -> None:
        if self.model != "htdemucs":
            raise NativeDemucsError("PROFILE_INVALID", "model must be htdemucs")
        if self.device != "cpu" or self.jobs != 1:
            raise NativeDemucsError("PROFILE_INVALID", "reference profile requires cpu and jobs=1")
        if not self.split:
            raise NativeDemucsError("PROFILE_INVALID", "upstream split mode must remain enabled")
        if not (0 < self.segment_seconds <= 7.8) or not float(self.segment_seconds).is_integer():
            raise NativeDemucsError(
                "PROFILE_INVALID",
                "Demucs 4.1.0 CLI requires segment_seconds to be a positive integer no greater than 7",
            )
        if not (0 <= self.overlap < 1):
            raise NativeDemucsError("PROFILE_INVALID", "overlap must be in [0,1)")
        if self.shifts != 0:
            raise NativeDemucsError("PROFILE_INVALID", "reference profile freezes shifts=0")
        if self.output_format != "wav" or not self.float32:
            raise NativeDemucsError("PROFILE_INVALID", "reference profile requires float32 WAV")
        if self.timeout_seconds <= 0:
            raise NativeDemucsError("PROFILE_INVALID", "timeout must be positive")


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _write_json(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def inspect_wav_format(path: Path) -> dict[str, int]:
    file_size = path.stat().st_size
    with path.open("rb") as handle:
        header = handle.read(12)
        if len(header) != 12 or header[:4] != b"RIFF" or header[8:12] != b"WAVE":
            raise NativeDemucsError("OUTPUT_FORMAT_INVALID", f"not a RIFF/WAVE file: {path}")
        fmt: dict[str, int] | None = None
        data_bytes: int | None = None
        while handle.tell() + 8 <= file_size:
            chunk_header = handle.read(8)
            if len(chunk_header) != 8:
                break
            chunk_id, chunk_size = struct.unpack("<4sI", chunk_header)
            payload_start = handle.tell()
            payload_end = payload_start + chunk_size
            if payload_end > file_size:
                raise NativeDemucsError("OUTPUT_FORMAT_INVALID", f"truncated WAV chunk in {path}")
            if chunk_id == b"fmt ":
                if chunk_size < 16:
                    raise NativeDemucsError("OUTPUT_FORMAT_INVALID", f"invalid fmt chunk in {path}")
                payload = handle.read(16)
                code, channels, sample_rate, byte_rate, block_align, bits = struct.unpack("<HHIIHH", payload)
                fmt = {
                    "format_code": code,
                    "channels": channels,
                    "sample_rate_hz": sample_rate,
                    "byte_rate": byte_rate,
                    "block_align": block_align,
                    "bits_per_sample": bits,
                }
                handle.seek(payload_end)
            else:
                if chunk_id == b"data":
                    data_bytes = chunk_size
                handle.seek(payload_end)
            if chunk_size % 2:
                if handle.tell() >= file_size:
                    raise NativeDemucsError("OUTPUT_FORMAT_INVALID", f"missing WAV pad byte in {path}")
                handle.seek(1, os.SEEK_CUR)
        if fmt is None or data_bytes is None:
            raise NativeDemucsError("OUTPUT_FORMAT_INVALID", f"WAV fmt or data chunk missing: {path}")
    block_align = fmt["block_align"]
    if block_align <= 0 or data_bytes % block_align != 0:
        raise NativeDemucsError("OUTPUT_FORMAT_INVALID", f"invalid WAV data alignment: {path}")
    fmt["data_bytes"] = data_bytes
    fmt["frames"] = data_bytes // block_align
    return fmt


def require_float32_stereo_wav(path: Path, *, expected_frames: int | None = None) -> dict[str, int]:
    info = inspect_wav_format(path)
    expected = {
        "format_code": EXPECTED_FORMAT_CODE,
        "channels": EXPECTED_CHANNELS,
        "sample_rate_hz": EXPECTED_SAMPLE_RATE,
        "bits_per_sample": EXPECTED_BITS_PER_SAMPLE,
        "block_align": EXPECTED_BLOCK_ALIGN,
    }
    for key, value in expected.items():
        if info.get(key) != value:
            raise NativeDemucsError(
                "OUTPUT_FORMAT_INVALID",
                f"{path.name} {key}: expected {value}, got {info.get(key)}",
            )
    expected_byte_rate = EXPECTED_SAMPLE_RATE * EXPECTED_BLOCK_ALIGN
    if info["byte_rate"] != expected_byte_rate:
        raise NativeDemucsError(
            "OUTPUT_FORMAT_INVALID",
            f"{path.name} byte_rate: expected {expected_byte_rate}, got {info['byte_rate']}",
        )
    if expected_frames is not None and info["frames"] != expected_frames:
        raise NativeDemucsError(
            "OUTPUT_DURATION_MISMATCH",
            f"{path.name} frames: expected {expected_frames}, got {info['frames']}",
        )
    return info


def validate_output_wavs(outputs: dict[str, Path]) -> dict[str, dict[str, int]]:
    formats: dict[str, dict[str, int]] = {}
    expected_frames: int | None = None
    for stem in EXPECTED_STEMS:
        path = outputs[stem]
        info = require_float32_stereo_wav(path, expected_frames=expected_frames)
        if expected_frames is None:
            expected_frames = info["frames"]
        formats[stem] = info
    return formats


def _read_audio_demucs(path: Path) -> tuple[Any, int, int]:
    """Decode through the pinned Demucs audio path and normalize to the model domain."""
    try:
        demucs_audio = importlib.import_module("demucs.audio")
    except ModuleNotFoundError as exc:
        raise NativeDemucsError(
            "METRICS_DEPENDENCY_MISSING",
            "the pinned Demucs runtime is required for normalized audio metrics",
        ) from exc
    try:
        audio_file = demucs_audio.AudioFile(path)
        original_sample_rate = int(audio_file.samplerate())
        tensor = audio_file.read(
            streams=0,
            samplerate=EXPECTED_SAMPLE_RATE,
            channels=EXPECTED_CHANNELS,
        )
        data = tensor.detach().cpu().numpy() if hasattr(tensor, "detach") else tensor
    except Exception as exc:
        raise NativeDemucsError("METRICS_DECODE_FAILED", f"failed to decode {path.name}: {exc}") from exc
    return data, EXPECTED_SAMPLE_RATE, original_sample_rate


def _compute_metrics_from_arrays(
    source_audio: Any,
    source_sample_rate: int,
    stem_audio: dict[str, Any],
    stem_sample_rates: dict[str, int],
    *,
    frame_samples: int = METRIC_FRAME_SAMPLES,
    source_original_sample_rate: int | None = None,
) -> dict[str, Any]:
    try:
        np = importlib.import_module("numpy")
    except ModuleNotFoundError as exc:
        raise NativeDemucsError("METRICS_DEPENDENCY_MISSING", "NumPy is required for normalized audio metrics") from exc
    if frame_samples <= 0:
        raise NativeDemucsError("METRICS_INVALID", "frame_samples must be positive")

    source = np.asarray(source_audio, dtype=np.float32)
    if source.ndim == 1:
        source = source[np.newaxis, :]
    if source.ndim != 2:
        raise NativeDemucsError("METRICS_SOURCE_SHAPE_INVALID", f"unexpected source shape: {source.shape}")
    if source.shape[0] == 1:
        source = np.repeat(source, 2, axis=0)
    elif source.shape[0] != EXPECTED_CHANNELS:
        raise NativeDemucsError("METRICS_SOURCE_SHAPE_INVALID", f"source channels: {source.shape[0]}")
    if source_sample_rate != EXPECTED_SAMPLE_RATE:
        raise NativeDemucsError(
            "METRICS_SAMPLE_RATE_MISMATCH",
            f"source sample rate: expected {EXPECTED_SAMPLE_RATE}, got {source_sample_rate}",
        )
    if source.shape[1] <= 0 or not np.isfinite(source).all():
        raise NativeDemucsError("METRICS_INVALID", "source is empty or non-finite")

    stems: list[Any] = []
    normalized_by_target: dict[str, Any] = {}
    for stem in EXPECTED_STEMS:
        sample_rate = stem_sample_rates[stem]
        if sample_rate != EXPECTED_SAMPLE_RATE:
            raise NativeDemucsError(
                "METRICS_SAMPLE_RATE_MISMATCH",
                f"{stem} sample rate: expected {EXPECTED_SAMPLE_RATE}, got {sample_rate}",
            )
        array = np.asarray(stem_audio[stem], dtype=np.float32)
        if array.ndim != 2 or array.shape[0] != EXPECTED_CHANNELS:
            raise NativeDemucsError("METRICS_STEM_SHAPE_INVALID", f"{stem} shape: {array.shape}")
        if array.shape[1] != source.shape[1]:
            raise NativeDemucsError(
                "METRICS_DURATION_MISMATCH",
                f"{stem} samples: expected {source.shape[1]}, got {array.shape[1]}",
            )
        if not np.isfinite(array).all():
            raise NativeDemucsError("METRICS_INVALID", f"{stem} contains NaN or Inf")
        normalized_by_target[stem] = array
        stems.append(array)

    source64 = source.astype(np.float64, copy=False)
    stacked = np.stack(stems, axis=0).astype(np.float64, copy=False)
    reconstruction = np.sum(stacked, axis=0)
    residual = source64 - reconstruction
    source_energy = float(np.mean(source64 * source64))
    residual_energy = float(np.mean(residual * residual))
    reconstruction_rms_error = math.sqrt(residual_energy)
    residual_energy_ratio = residual_energy / max(source_energy, 1e-24)

    activities: list[dict[str, Any]] = []
    total_samples = int(source.shape[1])
    for stem in EXPECTED_STEMS:
        array64 = normalized_by_target[stem].astype(np.float64, copy=False)
        frames: list[dict[str, Any]] = []
        for start in range(0, total_samples, frame_samples):
            end = min(total_samples, start + frame_samples)
            window = array64[:, start:end]
            rms = math.sqrt(float(np.mean(window * window)))
            peak = float(np.max(np.abs(window)))
            frames.append(
                {
                    "start_sample": start,
                    "end_sample": end,
                    "rms": rms,
                    "peak_abs": peak,
                    "evidence_class": "MEASURED",
                }
            )
        activities.append({"target": stem, "frames": frames, "evidence_class": "QUALITY_PROXY"})

    return {
        "reconstruction_rms_error": reconstruction_rms_error,
        "residual_to_mix_energy_ratio": residual_energy_ratio,
        "stem_activity": activities,
        "sample_rate_hz": EXPECTED_SAMPLE_RATE,
        "source_sample_rate_hz_original": (
            source_sample_rate if source_original_sample_rate is None else source_original_sample_rate
        ),
        "source_resampled": (
            source_original_sample_rate is not None
            and source_original_sample_rate != EXPECTED_SAMPLE_RATE
        ),
        "channels": EXPECTED_CHANNELS,
        "samples": total_samples,
        "frame_samples": frame_samples,
        "evidence_class": "QUALITY_PROXY",
        "authority_transfer": False,
    }


def compute_native_stem_metrics(
    source: Path,
    outputs: dict[str, Path],
    *,
    reader: Callable[[Path], tuple[Any, int, int]] | None = None,
) -> dict[str, Any]:
    read_audio = reader or _read_audio_demucs
    source_audio, source_sample_rate, source_original_sample_rate = read_audio(source)
    stem_audio: dict[str, Any] = {}
    stem_sample_rates: dict[str, int] = {}
    for stem in EXPECTED_STEMS:
        audio, sample_rate, _ = read_audio(outputs[stem])
        stem_audio[stem] = audio
        stem_sample_rates[stem] = sample_rate
    return _compute_metrics_from_arrays(
        source_audio,
        source_sample_rate,
        stem_audio,
        stem_sample_rates,
        source_original_sample_rate=source_original_sample_rate,
    )


def build_native_output_evidence(
    source: Path,
    outputs: dict[str, Path],
    *,
    reader: Callable[[Path], tuple[Any, int, int]] | None = None,
) -> tuple[dict[str, dict[str, int]], dict[str, Any]]:
    wav_formats = validate_output_wavs(outputs)
    metrics = compute_native_stem_metrics(source, outputs, reader=reader)
    expected_frames = next(iter(wav_formats.values()))["frames"]
    if metrics["samples"] != expected_frames:
        raise NativeDemucsError(
            "METRICS_DURATION_MISMATCH",
            f"decoded samples: expected {expected_frames}, got {metrics['samples']}",
        )
    return wav_formats, metrics


def _artifact_manifest(entries: list[tuple[Path, str]], root: Path) -> list[dict[str, Any]]:
    return [
        {
            "relative_path": path.relative_to(root).as_posix(),
            "sha256": sha256_file(path),
            "byte_size": path.stat().st_size,
            "evidence_class": evidence_class,
        }
        for path, evidence_class in sorted(entries, key=lambda item: item[0].relative_to(root).as_posix())
    ]


def build_command(profile: NativeDemucsProfile, source: Path, output_root: Path) -> list[str]:
    profile.validate()
    command = [
        *profile.entrypoint,
        "--name", profile.model,
        "--device", profile.device,
        "--jobs", str(profile.jobs),
        "--segment", str(int(profile.segment_seconds)),
        "--overlap", str(profile.overlap),
        "--shifts", str(profile.shifts),
        "--out", str(output_root),
        "--filename", "{stem}.{ext}",
    ]
    if profile.float32:
        command.append("--float32")
    command.append(str(source))
    return command


def _find_outputs(root: Path) -> dict[str, Path]:
    found: dict[str, Path] = {}
    for stem in EXPECTED_STEMS:
        matches = [path for path in root.rglob(f"{stem}.wav") if path.is_file()]
        if len(matches) != 1:
            raise NativeDemucsError("OUTPUT_SET_INVALID", f"expected one {stem}.wav, found {len(matches)}")
        found[stem] = matches[0]
    return found


def run_native_demucs(profile: NativeDemucsProfile, source: Path, output_dir: Path) -> dict[str, Any]:
    profile.validate()
    source = source.resolve(strict=True)
    output_dir = output_dir.resolve()
    source_hash = sha256_file(source)
    if profile.source_sha256 and source_hash != profile.source_sha256:
        raise NativeDemucsError("SOURCE_HASH_MISMATCH", "source SHA-256 does not match frozen profile")
    executable = shutil.which(profile.entrypoint[0])
    if executable is None:
        raise NativeDemucsError("EXECUTABLE_NOT_FOUND", profile.entrypoint[0])
    if output_dir.exists():
        raise NativeDemucsError("OUTPUT_EXISTS", str(output_dir))

    stage = output_dir.with_name(f".{output_dir.name}.stage")
    if stage.exists():
        shutil.rmtree(stage)
    stage.mkdir(parents=True)
    command = build_command(profile, source, stage)
    started = time.monotonic()
    proc = subprocess.Popen(
        command,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        start_new_session=True,
        env={**os.environ, "HF_HUB_OFFLINE": "1", "TRANSFORMERS_OFFLINE": "1"},
    )
    try:
        stdout, stderr = proc.communicate(timeout=profile.timeout_seconds)
    except subprocess.TimeoutExpired:
        os.killpg(proc.pid, signal.SIGTERM)
        try:
            stdout, stderr = proc.communicate(timeout=10)
        except subprocess.TimeoutExpired:
            os.killpg(proc.pid, signal.SIGKILL)
            stdout, stderr = proc.communicate()
        raise NativeDemucsError(
            "NATIVE_PROCESS_TIMEOUT",
            "Demucs exceeded the frozen timeout",
            details={"stdout": stdout, "stderr": stderr, "elapsed_seconds": time.monotonic() - started},
        )

    elapsed = time.monotonic() - started
    if proc.returncode != 0:
        raise NativeDemucsError(
            "NATIVE_PROCESS_FAILED",
            f"Demucs exited with {proc.returncode}",
            details={"stdout": stdout, "stderr": stderr, "elapsed_seconds": elapsed},
        )

    outputs = _find_outputs(stage)
    wav_formats, metrics = build_native_output_evidence(source, outputs)

    analysis_path = stage / "analysis" / "stem-metrics.json"
    _write_json(analysis_path, metrics)
    stdout_path = stage / "stdout.log"
    stderr_path = stage / "stderr.log"
    stdout_path.write_text(stdout, encoding="utf-8")
    stderr_path.write_text(stderr, encoding="utf-8")

    stems = {
        stem: {
            "path": str(path.relative_to(stage)),
            "sha256": sha256_file(path),
            "bytes": path.stat().st_size,
            "wav_format": wav_formats[stem],
            "evidence_class": "MODEL_ESTIMATE",
        }
        for stem, path in outputs.items()
    }
    receipt = {
        "schema_version": "0.2.0",
        "status": "COMPLETE",
        "profile_id": profile.profile_id,
        "source": {
            "path": str(source),
            "sha256": source_hash,
            "byte_size": source.stat().st_size,
        },
        "command": command,
        "elapsed_seconds": elapsed,
        "stdout": "stdout.log",
        "stderr": "stderr.log",
        "stems": stems,
        "metrics": {
            "relative_path": "analysis/stem-metrics.json",
            "reconstruction_rms_error": metrics["reconstruction_rms_error"],
            "residual_to_mix_energy_ratio": metrics["residual_to_mix_energy_ratio"],
            "sample_rate_hz": metrics["sample_rate_hz"],
            "source_sample_rate_hz_original": metrics["source_sample_rate_hz_original"],
            "source_resampled": metrics["source_resampled"],
            "channels": metrics["channels"],
            "samples": metrics["samples"],
            "evidence_class": metrics["evidence_class"],
        },
        "output_encoding": "WAV_FLOAT32",
        "runtime_admission": False,
        "pilot_authorized": False,
        "authority_transfer": False,
    }
    receipt_path = stage / "run-receipt.json"
    _write_json(receipt_path, receipt)

    artifact_manifest = _artifact_manifest(
        [
            *((path, "MODEL_ESTIMATE") for path in outputs.values()),
            (analysis_path, "QUALITY_PROXY"),
            (stdout_path, "EXECUTION_LOG"),
            (stderr_path, "EXECUTION_LOG"),
            (receipt_path, "EXECUTION_RECEIPT"),
        ],
        stage,
    )
    stage.replace(output_dir)
    return {
        "status": "COMPLETE",
        "command": command,
        "elapsed_seconds": elapsed,
        "stdout": stdout,
        "stderr": stderr,
        "artifacts": stems,
        "wav_validation": wav_formats,
        "metrics": metrics,
        "evidence_files": {
            "metrics": "analysis/stem-metrics.json",
            "receipt": "run-receipt.json",
            "stdout": "stdout.log",
            "stderr": "stderr.log",
        },
        "artifact_manifest": artifact_manifest,
        "runtime_admission": False,
        "pilot_authorized": False,
        "authority_transfer": False,
    }
