from __future__ import annotations

from pathlib import Path

import pytest

import aios_tools.audio_orchestrator as orchestrator


def _payload(tmp_path: Path) -> dict:
    return {
        "run_id": "S2-TEST-ORCH-001",
        "profile_id": "slice2-stem-section-v0.1",
        "profile_checksum": "26ac1b86891a8dd7775a3b25bdb7f4b00d9ab284c7575815ce43c5f14e19680f",
        "source_audio_path": str(tmp_path / "source.wav"),
        "source_sha256": "0" * 64,
        "slice1_receipt_path": str(tmp_path / "slice1.md"),
        "slice1_run_id": "S1-TEST",
        "slice1_source_sha256": "0" * 64,
        "profile_path": str(tmp_path / "profile.json"),
        "model_cache_directory": str(tmp_path / "cache"),
        "output_directory": str(tmp_path / "output"),
        "scope": "udio-algorithms",
        "requested_by": "test",
    }


def test_orchestrator_promotes_complete_stem_set(monkeypatch, tmp_path: Path):
    payload = _payload(tmp_path)
    output = tmp_path / "output"

    monkeypatch.setattr(
        orchestrator,
        "preflight_audio_runtime",
        lambda value: {
            "source": {"path": str(tmp_path / "source.wav")},
            "slice1_dependency": {"run_id": "S1-TEST"},
            "model_cache": {"directory": str(tmp_path / "cache")},
            "output_transaction": {"output_directory": str(output)},
        },
    )

    def fake_inference(*, source_path, model_cache, transaction):
        specs = []
        stems = []
        for target in ("vocals", "drums", "bass", "other"):
            relative = f"stems/{target}.wav"
            transaction.artifact_path(relative).write_bytes(b"RIFF" + target.encode())
            specs.append(orchestrator.ArtifactSpec(relative, "audio/wav", "MODEL_ESTIMATE"))
            stems.append({"target": target, "relative_path": relative})
        return {
            "targets": ["vocals", "drums", "bass", "other"],
            "stems": stems,
            "metrics": {
                "reconstruction_rms_error": 0.0,
                "residual_to_mix_energy_ratio": 0.0,
                "stem_activity": [],
                "evidence_class": "QUALITY_PROXY",
                "authority_transfer": False,
            },
            "artifact_specs": specs,
        }

    monkeypatch.setattr(orchestrator, "run_frozen_stem_inference", fake_inference)
    monkeypatch.setattr(orchestrator, "validate_result_contract", lambda value: None)

    result = orchestrator.run_basic_stem_split(payload)
    assert result["status"] == "COMPLETE"
    assert result["authority_transfer"] is False
    assert output.is_dir()
    assert (output / "artifact-manifest.json").is_file()
    assert (output / "run-receipt.json").is_file()
    assert (output / "analysis" / "stem-metrics.json").is_file()
    for target in ("vocals", "drums", "bass", "other"):
        assert (output / "stems" / f"{target}.wav").is_file()


def test_orchestrator_rolls_back_when_inference_fails(monkeypatch, tmp_path: Path):
    payload = _payload(tmp_path)
    output = tmp_path / "output"
    monkeypatch.setattr(
        orchestrator,
        "preflight_audio_runtime",
        lambda value: {
            "source": {"path": str(tmp_path / "source.wav")},
            "slice1_dependency": {"run_id": "S1-TEST"},
            "model_cache": {"directory": str(tmp_path / "cache")},
            "output_transaction": {"output_directory": str(output)},
        },
    )

    def fail(**kwargs):
        raise orchestrator.AudioInferenceError("SEPARATION_RUNTIME_ERROR", "boom")

    monkeypatch.setattr(orchestrator, "run_frozen_stem_inference", fail)
    with pytest.raises(orchestrator.AudioOrchestrationError, match="boom"):
        orchestrator.run_basic_stem_split(payload)
    assert not output.exists()
    assert not any(path.name.startswith(".output.S2-TEST-ORCH-001.") for path in tmp_path.iterdir())
