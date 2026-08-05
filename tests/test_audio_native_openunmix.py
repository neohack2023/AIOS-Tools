from __future__ import annotations

import json
from pathlib import Path

import pytest

from aios_tools.audio_native_openunmix import (
    EXPECTED_TARGETS,
    NativeOpenUnmixError,
    NativeOpenUnmixProfile,
    build_command,
    sha256_file,
)


def profile(**overrides):
    values = {
        "profile_id": "openunmix-umxhq-native-cpu-v0.1",
        "executable": "umx",
        "model": "umxhq",
        "targets": EXPECTED_TARGETS,
        "no_cuda": True,
        "niter": 1,
        "wiener_win_len": 300,
        "filterbank": "torch",
        "extension": "wav",
        "timeout_seconds": 900,
        "source_sha256": None,
    }
    values.update(overrides)
    return NativeOpenUnmixProfile(**values)


def test_frozen_command_is_exact_and_shell_free(tmp_path: Path):
    command = build_command(profile(), tmp_path / "source.wav", tmp_path / "out")
    assert command == [
        "umx",
        str(tmp_path / "source.wav"),
        "--model",
        "umxhq",
        "--targets",
        "vocals",
        "drums",
        "bass",
        "other",
        "--outdir",
        str(tmp_path / "out"),
        "--ext",
        "wav",
        "--niter",
        "1",
        "--wiener-win-len",
        "300",
        "--filterbank",
        "torch",
        "--verbose",
        "--no-cuda",
    ]


def test_profile_rejects_target_drift():
    with pytest.raises(NativeOpenUnmixError, match="targets"):
        profile(targets=("vocals", "other")).validate()


def test_profile_rejects_gpu_reference_execution():
    with pytest.raises(NativeOpenUnmixError, match="no_cuda"):
        profile(no_cuda=False).validate()


def test_profile_round_trip(tmp_path: Path):
    path = tmp_path / "profile.json"
    path.write_text(
        json.dumps(
            {
                "profile_id": "openunmix-umxhq-native-cpu-v0.1",
                "executable": "umx",
                "model": "umxhq",
                "targets": list(EXPECTED_TARGETS),
                "no_cuda": True,
                "niter": 1,
                "wiener_win_len": 300,
                "filterbank": "torch",
                "extension": "wav",
                "timeout_seconds": 900,
                "source_sha256": None,
            }
        ),
        encoding="utf-8",
    )
    loaded = NativeOpenUnmixProfile.from_json(path)
    loaded.validate()
    assert loaded.targets == EXPECTED_TARGETS


def test_sha256_file(tmp_path: Path):
    path = tmp_path / "fixture.bin"
    path.write_bytes(b"abc")
    assert sha256_file(path) == "ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad"
