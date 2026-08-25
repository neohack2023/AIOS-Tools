from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

from .audio_inference import AudioInferenceError, run_frozen_stem_inference
from .audio_runtime import AudioRuntimeError, preflight_audio_runtime, validate_result_contract
from .audio_transaction import ArtifactSpec, AudioArtifactTransaction, AudioTransactionError


class AudioOrchestrationError(RuntimeError):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message


def _write_json(path: Path, value: dict[str, Any]) -> None:
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def run_basic_stem_split(payload: dict[str, Any]) -> dict[str, Any]:
    """Run preflight, frozen four-stem inference, evidence freeze, and atomic promotion.

    This remains an internal runtime function. It does not register or admit the tool.
    """
    started = time.perf_counter()
    transaction: AudioArtifactTransaction | None = None
    try:
        preflight = preflight_audio_runtime(payload)
        output_directory = Path(preflight["output_transaction"]["output_directory"])
        transaction = AudioArtifactTransaction(
            output_directory=output_directory,
            run_id=payload["run_id"],
            profile_id=payload["profile_id"],
            profile_checksum=payload["profile_checksum"],
            authority_transfer=False,
        )
        transaction.prepare()
        inference = run_frozen_stem_inference(
            source_path=Path(preflight["source"]["path"]),
            model_cache=Path(preflight["model_cache"]["directory"]),
            transaction=transaction,
        )

        metrics_path = transaction.artifact_path("analysis/stem-metrics.json")
        _write_json(metrics_path, inference["metrics"])
        receipt = {
            "schema_version": "0.2.0",
            "status": "BASIC_STEM_SPLIT_STAGED",
            "run_id": payload["run_id"],
            "tool_identity": "audio.stem_section_analyze",
            "profile_id": payload["profile_id"],
            "profile_checksum": payload["profile_checksum"],
            "source": preflight["source"],
            "slice1_dependency": preflight["slice1_dependency"],
            "model_cache": preflight["model_cache"],
            "stems": inference["stems"],
            "metrics": inference["metrics"],
            "output_encoding": "WAV_FLOAT32",
            "elapsed_seconds": round(time.perf_counter() - started, 6),
            "runtime_admission": False,
            "pilot_authorized": False,
            "authority_transfer": False,
        }
        receipt_path = transaction.artifact_path("run-receipt.json")
        _write_json(receipt_path, receipt)

        specs = list(inference["artifact_specs"])
        specs.extend(
            [
                ArtifactSpec("analysis/stem-metrics.json", "application/json", "QUALITY_PROXY"),
                ArtifactSpec("run-receipt.json", "application/json", "EXECUTION_RECEIPT"),
            ]
        )
        manifest = transaction.build_manifest(specs)
        promoted = transaction.promote()

        result = {
            "schema_version": "0.1.0",
            "status": "COMPLETE",
            "run_id": payload["run_id"],
            "tool_identity": "audio.stem_section_analyze",
            "profile_id": payload["profile_id"],
            "profile_checksum": payload["profile_checksum"],
            "output_directory": str(promoted),
            "targets": inference["targets"],
            "stems": inference["stems"],
            "artifact_manifest": manifest,
            "runtime_admission": False,
            "pilot_authorized": False,
            "authority_transfer": False,
        }
        validate_result_contract(result)
        return result
    except (AudioRuntimeError, AudioInferenceError, AudioTransactionError) as exc:
        if transaction is not None and transaction.state not in {"PROMOTED", "ROLLED_BACK"}:
            transaction.rollback()
        raise AudioOrchestrationError(exc.code, exc.message) from exc
    except Exception as exc:
        if transaction is not None and transaction.state not in {"PROMOTED", "ROLLED_BACK"}:
            transaction.rollback()
        raise AudioOrchestrationError("UNEXPECTED_RUNTIME_ERROR", str(exc)) from exc
