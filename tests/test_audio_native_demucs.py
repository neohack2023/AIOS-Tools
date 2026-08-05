from pathlib import Path

import pytest

from aios_tools.audio_native_demucs import NativeDemucsError, NativeDemucsProfile, build_command


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


def test_build_command_freezes_upstream_segmentation() -> None:
    command = build_command(profile(), Path("/tmp/source.wav"), Path("/tmp/out"))
    assert command[:3] == ["python", "-m", "demucs"]
    assert command[command.index("--name") + 1] == "htdemucs"
    assert command[command.index("--segment") + 1] == "7.8"
    assert command[command.index("--overlap") + 1] == "0.1"
    assert command[command.index("--shifts") + 1] == "0"
    assert "--float32" in command
    assert command[-1] == "/tmp/source.wav"


def test_profile_rejects_custom_non_upstream_split_path() -> None:
    invalid = profile().__class__(**{**profile().__dict__, "split": False})
    with pytest.raises(NativeDemucsError) as error:
        invalid.validate()
    assert error.value.code == "PROFILE_INVALID"


def test_profile_rejects_parallel_cpu_jobs() -> None:
    invalid = profile().__class__(**{**profile().__dict__, "jobs": 2})
    with pytest.raises(NativeDemucsError):
        invalid.validate()
