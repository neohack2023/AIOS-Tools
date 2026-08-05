from __future__ import annotations

import json
from pathlib import Path

import pytest

from aios_tools.audio_transaction import ArtifactSpec, AudioArtifactTransaction, AudioTransactionError


def test_transaction_promotes_complete_manifest_atomically(tmp_path: Path):
    output = tmp_path / "run-output"
    transaction = AudioArtifactTransaction(output_directory=output, run_id="S2-TEST-001")
    transaction.prepare()
    transaction.artifact_path("stems/vocals.wav").write_bytes(b"RIFF-data")
    transaction.artifact_path("metrics.json").write_text("{}\n", encoding="utf-8")
    manifest = transaction.build_manifest(
        [
            ArtifactSpec("stems/vocals.wav", "audio/wav", "MODEL_ESTIMATE"),
            ArtifactSpec("metrics.json", "application/json", "MEASURED"),
        ]
    )
    assert manifest["complete"] is True
    assert manifest["authority_transfer"] is False
    promoted = transaction.promote()
    assert promoted == output
    assert transaction.state == "PROMOTED"
    stored = json.loads((output / "artifact-manifest.json").read_text(encoding="utf-8"))
    assert stored["transaction_state"] == "FROZEN"
    assert len(stored["artifacts"]) == 2


def test_context_manager_rolls_back_on_failure(tmp_path: Path):
    output = tmp_path / "failed-output"
    transaction = AudioArtifactTransaction(output_directory=output, run_id="S2-TEST-002")
    with pytest.raises(RuntimeError, match="boom"):
        with transaction:
            transaction.artifact_path("partial.bin").write_bytes(b"partial")
            raise RuntimeError("boom")
    assert transaction.state == "ROLLED_BACK"
    assert not output.exists()
    assert not any(path.name.startswith(".failed-output.S2-TEST-002.") for path in tmp_path.iterdir())


def test_missing_required_artifact_fails_closed(tmp_path: Path):
    transaction = AudioArtifactTransaction(output_directory=tmp_path / "out", run_id="S2-TEST-003")
    transaction.prepare()
    with pytest.raises(AudioTransactionError, match="required artifact missing"):
        transaction.build_manifest([ArtifactSpec("stems/bass.wav", "audio/wav", "MODEL_ESTIMATE")])
    transaction.rollback()


def test_existing_output_is_never_overwritten(tmp_path: Path):
    output = tmp_path / "out"
    output.mkdir()
    transaction = AudioArtifactTransaction(output_directory=output, run_id="S2-TEST-004")
    with pytest.raises(AudioTransactionError, match="output already exists"):
        transaction.prepare()


def test_artifact_escape_is_rejected(tmp_path: Path):
    transaction = AudioArtifactTransaction(output_directory=tmp_path / "out", run_id="S2-TEST-005")
    transaction.prepare()
    with pytest.raises(AudioTransactionError, match="unsafe component"):
        transaction.artifact_path("../escape.bin")
    transaction.rollback()


def test_duplicate_artifact_declaration_is_rejected(tmp_path: Path):
    transaction = AudioArtifactTransaction(output_directory=tmp_path / "out", run_id="S2-TEST-006")
    transaction.prepare()
    transaction.artifact_path("metrics.json").write_text("{}\n", encoding="utf-8")
    specs = [
        ArtifactSpec("metrics.json", "application/json", "MEASURED"),
        ArtifactSpec("metrics.json", "application/json", "MEASURED"),
    ]
    with pytest.raises(AudioTransactionError, match="duplicate artifact declaration"):
        transaction.build_manifest(specs)
    transaction.rollback()
