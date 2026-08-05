from __future__ import annotations

import struct
from pathlib import Path
from typing import Any


class AudioWavError(RuntimeError):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message


def write_float32_wav(path: Path, audio: Any, sample_rate: int) -> dict[str, int]:
    """Write a mono or stereo IEEE-float WAV without codec indirection."""
    array = audio.detach().cpu().numpy() if hasattr(audio, "detach") else audio
    try:
        import numpy as np
    except ModuleNotFoundError as exc:
        raise AudioWavError("ARTIFACT_WRITE_FAILED", "NumPy is required for float32 WAV output") from exc
    array = np.asarray(array, dtype="<f4")
    if array.ndim != 2:
        raise AudioWavError("ARTIFACT_WRITE_FAILED", f"audio must be channels x samples, got shape {array.shape}")
    channels, samples = array.shape
    if channels not in (1, 2) or samples <= 0:
        raise AudioWavError("ARTIFACT_WRITE_FAILED", f"unsupported WAV shape: {array.shape}")
    if sample_rate <= 0:
        raise AudioWavError("ARTIFACT_WRITE_FAILED", "sample rate must be positive")
    interleaved = np.ascontiguousarray(array.T, dtype="<f4").tobytes(order="C")
    block_align = channels * 4
    byte_rate = sample_rate * block_align
    fmt = struct.pack("<HHIIHH", 3, channels, sample_rate, byte_rate, block_align, 32)
    fact = struct.pack("<I", samples)
    riff_size = 4 + (8 + len(fmt)) + (8 + len(fact)) + (8 + len(interleaved))
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("wb") as handle:
        handle.write(b"RIFF")
        handle.write(struct.pack("<I", riff_size))
        handle.write(b"WAVE")
        handle.write(b"fmt ")
        handle.write(struct.pack("<I", len(fmt)))
        handle.write(fmt)
        handle.write(b"fact")
        handle.write(struct.pack("<I", len(fact)))
        handle.write(fact)
        handle.write(b"data")
        handle.write(struct.pack("<I", len(interleaved)))
        handle.write(interleaved)
    return inspect_wav_format(path)


def inspect_wav_format(path: Path) -> dict[str, int]:
    payload = path.read_bytes()
    if len(payload) < 44 or payload[:4] != b"RIFF" or payload[8:12] != b"WAVE":
        raise AudioWavError("ARTIFACT_FORMAT_INVALID", f"not a RIFF/WAVE file: {path}")
    offset = 12
    fmt: dict[str, int] | None = None
    data_bytes = -1
    while offset + 8 <= len(payload):
        chunk_id = payload[offset:offset + 4]
        chunk_size = struct.unpack_from("<I", payload, offset + 4)[0]
        start = offset + 8
        end = start + chunk_size
        if end > len(payload):
            raise AudioWavError("ARTIFACT_FORMAT_INVALID", f"truncated WAV chunk in {path}")
        if chunk_id == b"fmt ":
            if chunk_size < 16:
                raise AudioWavError("ARTIFACT_FORMAT_INVALID", f"invalid fmt chunk in {path}")
            code, channels, sample_rate, _, block_align, bits = struct.unpack_from("<HHIIHH", payload, start)
            fmt = {
                "format_code": code,
                "channels": channels,
                "sample_rate_hz": sample_rate,
                "block_align": block_align,
                "bits_per_sample": bits,
            }
        elif chunk_id == b"data":
            data_bytes = chunk_size
        offset = end + (chunk_size % 2)
    if fmt is None or data_bytes < 0:
        raise AudioWavError("ARTIFACT_FORMAT_INVALID", f"WAV fmt or data chunk missing: {path}")
    fmt["data_bytes"] = data_bytes
    return fmt


def require_float32_stereo_wav(path: Path, sample_rate: int, samples: int) -> dict[str, int]:
    info = inspect_wav_format(path)
    expected = {
        "format_code": 3,
        "channels": 2,
        "sample_rate_hz": sample_rate,
        "bits_per_sample": 32,
        "block_align": 8,
        "data_bytes": samples * 8,
    }
    for key, value in expected.items():
        if info.get(key) != value:
            raise AudioWavError("ARTIFACT_FORMAT_INVALID", f"{path.name} {key}: expected {value}, got {info.get(key)}")
    return info
