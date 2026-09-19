from __future__ import annotations

import struct
from pathlib import Path

import numpy as np
import pytest

from aios_tools.audio_native_demucs import (
    EXPECTED_STEMS,
    NativeDemucsError,
    NativeDemucsProfile,
    _compute_metrics_from_arrays,
    build_command,
    build_native_output_evidence,
    require_float32_stereo_wav,
    validate_output_wavs,
)


def profile() -> NativeDemucsProfile:
    return NativeDemucsProfile(
        profile_id="demucs-htdemucs-native-cpu-v0.1",
        entrypoint=("python", "-m", "demucs"),
        model="htdemucs",
        device="cpu",
        jobs=1,
        split=True,
        segment_seconds=7.8,
        overlap=0.1,
        shifts=0,
        output_format="wav",
        float32=True,
        timeout_seconds=1200,
        source_sha256=None,
    )


def _write_wav(
    path: Path,
    *,
    frames: int = 32,
    format_code: int = 3,
    channels: int = 2,
    sample_rate: int = 44100,
    bits_per_sample: int = 32,
) -> None:
    if format_code == 3 and bits_per_sample == 32:
        data = struct.pack("<" + ("f" * frames * channels), *([0.0] * frames * channels))
        block_align = channels * 4
    elif format_code == 1 and bits_per_sample == 16:
        data = bytes(frames * channels * 2)
        block_align = channels * 2
    else:
        raise AssertionError("unsupported test WAV fixture")
    byte_rate = sample_rate * block_align
    fmt = struct.pack("<HHIIHH", format_code, channels, sample_rate, byte_rate, block_align, bits_per_sample)
    riff_size = 4 + (8 + len(fmt)) + (8 + len(data))
    path.write_bytes(
        b"RIFF"
        + struct.pack("<I", riff_size)
        + b"WAVE"
        + b"fmt "
        + struct.pack("<I", len(fmt))
        + fmt
        + b"data"
        + struct.pack("<I", len(data))
        + data
    )


def test_build_command_freezes_upstream_segmentation() -> None:
    source = Path("/tmp/source.wav")
    command = build_command(profile(), source, Path("/tmp/out"))
    assert command[:3] == ["python", "-m", "demucs"]
    assert command[command.index("--name") + 1] == "htdemucs"
    assert command[command.index("--segment") + 1] == "7.8"
    assert command[command.index("--overlap") + 1] == "0.1"
    assert command[command.index("--shifts") + 1] == "0"
    assert "--float32" in command
    assert command[-1] == str(source)


def test_profile_rejects_custom_non_upstream_split_path() -> None:
    invalid = profile().__class__(**{**profile().__dict__, "split": False})
    with pytest.raises(NativeDemucsError) as error:
        invalid.validate()
    assert error.value.code == "PROFILE_INVALID"


def test_profile_rejects_parallel_cpu_jobs() -> None:
    invalid = profile().__class__(**{**profile().__dict__, "jobs": 2})
    with pytest.raises(NativeDemucsError):
        invalid.validate()


def test_wav_validation_accepts_ieee_float32_stereo(tmp_path: Path) -> None:
    path = tmp_path / "stem.wav"
    _write_wav(path, frames=32)
    info = require_float32_stereo_wav(path)
    assert info["format_code"] == 3
    assert info["channels"] == 2
    assert info["sample_rate_hz"] == 44100
    assert info["bits_per_sample"] == 32
    assert info["frames"] == 32


def test_wav_validation_rejects_pcm16(tmp_path: Path) -> None:
    path = tmp_path / "stem.wav"
    _write_wav(path, format_code=1, bits_per_sample=16)
    with pytest.raises(NativeDemucsError) as error:
        require_float32_stereo_wav(path)
    assert error.value.code == "OUTPUT_FORMAT_INVALID"


def test_output_set_rejects_frame_mismatch(tmp_path: Path) -> None:
    outputs: dict[str, Path] = {}
    for stem in EXPECTED_STEMS:
        path = tmp_path / f"{stem}.wav"
        _write_wav(path, frames=33 if stem == "vocals" else 32)
        outputs[stem] = path
    with pytest.raises(NativeDemucsError) as error:
        validate_output_wavs(outputs)
    assert error.value.code == "OUTPUT_DURATION_MISMATCH"


def test_metrics_use_mean_square_energy_ratio() -> None:
    source = np.ones((2, 8), dtype=np.float32)
    stem_audio = {stem: np.zeros((2, 8), dtype=np.float32) for stem in EXPECTED_STEMS}
    stem_audio["drums"] = np.full((2, 8), 0.5, dtype=np.float32)
    stem_audio["bass"] = np.full((2, 8), 0.25, dtype=np.float32)
    stem_sample_rates = {stem: 44100 for stem in EXPECTED_STEMS}

    metrics = _compute_metrics_from_arrays(
        source,
        44100,
        stem_audio,
        stem_sample_rates,
        frame_samples=4,
    )

    assert metrics["reconstruction_rms_error"] == pytest.approx(0.25)
    assert metrics["residual_to_mix_energy_ratio"] == pytest.approx(0.0625)
    assert metrics["samples"] == 8
    assert metrics["stem_activity"][0]["frames"][0]["rms"] == pytest.approx(0.5)


def test_metrics_reject_source_sample_rate_drift() -> None:
    source = np.zeros((2, 8), dtype=np.float32)
    stem_audio = {stem: np.zeros((2, 8), dtype=np.float32) for stem in EXPECTED_STEMS}
    stem_sample_rates = {stem: 44100 for stem in EXPECTED_STEMS}
    with pytest.raises(NativeDemucsError) as error:
        _compute_metrics_from_arrays(source, 48000, stem_audio, stem_sample_rates)
    assert error.value.code == "METRICS_SAMPLE_RATE_MISMATCH"


def test_output_evidence_binds_wav_headers_and_decoded_metrics(tmp_path: Path) -> None:
    source_path = tmp_path / "source.mp3"
    source_path.write_bytes(b"source")
    outputs: dict[str, Path] = {}
    for stem in EXPECTED_STEMS:
        path = tmp_path / f"{stem}.wav"
        _write_wav(path, frames=8)
        outputs[stem] = path

    source_audio = np.ones((2, 8), dtype=np.float32)
    decoded = {stem: np.zeros((2, 8), dtype=np.float32) for stem in EXPECTED_STEMS}
    decoded["drums"] = source_audio.copy()

    def reader(path: Path):
        if path == source_path:
            return source_audio, 44100
        return decoded[path.stem], 44100

    formats, metrics = build_native_output_evidence(source_path, outputs, reader=reader)

    assert {formats[stem]["frames"] for stem in EXPECTED_STEMS} == {8}
    assert metrics["reconstruction_rms_error"] == pytest.approx(0.0)
    assert metrics["residual_to_mix_energy_ratio"] == pytest.approx(0.0)
