from __future__ import annotations

import struct
from pathlib import Path

import pytest

from aios_tools.audio_wav import AudioWavError, inspect_wav_format, require_float32_stereo_wav, write_float32_wav


def test_writer_produces_verified_ieee_float32_stereo(tmp_path: Path):
    np = pytest.importorskip("numpy")
    audio = np.zeros((2, 32), dtype=np.float32)
    path = tmp_path / "stem.wav"
    info = write_float32_wav(path, audio, 44100)
    assert info == {
        "format_code": 3,
        "channels": 2,
        "sample_rate_hz": 44100,
        "block_align": 8,
        "bits_per_sample": 32,
        "data_bytes": 256,
    }
    assert require_float32_stereo_wav(path, 44100, 32) == info
    payload = path.read_bytes()
    assert struct.unpack_from("<H", payload, payload.index(b"fmt ") + 8)[0] == 3


def test_profile_validator_rejects_pcm16(tmp_path: Path):
    path = tmp_path / "pcm16.wav"
    fmt = struct.pack("<HHIIHH", 1, 2, 44100, 176400, 4, 16)
    data = bytes(64)
    riff_size = 4 + 8 + len(fmt) + 8 + len(data)
    path.write_bytes(b"RIFF" + struct.pack("<I", riff_size) + b"WAVEfmt " + struct.pack("<I", len(fmt)) + fmt + b"data" + struct.pack("<I", len(data)) + data)
    assert inspect_wav_format(path)["format_code"] == 1
    with pytest.raises(AudioWavError, match="format_code"):
        require_float32_stereo_wav(path, 44100, 16)


def test_writer_rejects_invalid_rank(tmp_path: Path):
    np = pytest.importorskip("numpy")
    with pytest.raises(AudioWavError, match="channels x samples"):
        write_float32_wav(tmp_path / "bad.wav", np.zeros((1, 2, 3), dtype=np.float32), 44100)
