from __future__ import annotations

from pathlib import Path

import pytest

from aios_tools.audio_inference import (
    AudioInferenceError,
    EXPECTED_SAMPLE_RATE,
    LEGACY_WEIGHT_KEYS,
    _filtered_state_dict,
    _require_runtime_modules,
)


class FakeModel:
    def state_dict(self):
        return {"layer.weight": object(), "layer.bias": object()}


def test_filtered_state_dict_accepts_only_known_legacy_keys():
    state = {
        "layer.weight": 1,
        "layer.bias": 2,
        "sample_rate": EXPECTED_SAMPLE_RATE,
        "stft.window": 3,
        "transform.0.window": 4,
    }
    filtered = _filtered_state_dict(FakeModel(), state, "vocals")
    assert filtered == {"layer.weight": 1, "layer.bias": 2}
    assert set(state) - set(filtered) == LEGACY_WEIGHT_KEYS


def test_filtered_state_dict_rejects_missing_model_keys():
    state = {
        "layer.weight": 1,
        "sample_rate": EXPECTED_SAMPLE_RATE,
        "stft.window": 3,
        "transform.0.window": 4,
    }
    with pytest.raises(AudioInferenceError, match="missing model keys"):
        _filtered_state_dict(FakeModel(), state, "drums")


def test_filtered_state_dict_rejects_unknown_extra_keys():
    state = {
        "layer.weight": 1,
        "layer.bias": 2,
        "sample_rate": EXPECTED_SAMPLE_RATE,
        "stft.window": 3,
        "transform.0.window": 4,
        "surprise": 5,
    }
    with pytest.raises(AudioInferenceError, match="unexpected keys"):
        _filtered_state_dict(FakeModel(), state, "bass")


def test_filtered_state_dict_rejects_wrong_sample_rate():
    state = {
        "layer.weight": 1,
        "layer.bias": 2,
        "sample_rate": 48000,
        "stft.window": 3,
        "transform.0.window": 4,
    }
    with pytest.raises(AudioInferenceError, match="not 44100 Hz"):
        _filtered_state_dict(FakeModel(), state, "other")


def test_runtime_dependency_failure_is_fail_closed(monkeypatch):
    import aios_tools.audio_inference as module

    real_import = module.importlib.import_module

    def fake_import(name: str):
        if name == "torch":
            raise ModuleNotFoundError("torch missing", name="torch")
        return real_import(name)

    monkeypatch.setattr(module.importlib, "import_module", fake_import)
    with pytest.raises(AudioInferenceError, match="required runtime dependency is missing"):
        _require_runtime_modules()
