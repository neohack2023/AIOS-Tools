from __future__ import annotations

import hashlib
import importlib.util
import json
import sys
import types
from pathlib import Path

import pytest

from aios_tools.benchmarks.bfcl_package import (
    BFCL_PIN,
    BFCLPackageError,
    RUN_CLASSIFICATION,
    create_bfcl_ab_package,
    load_case_map,
)
from aios_tools.benchmarks.compare import (
    ScoreComparisonError,
    compare_score_artifacts,
)
from aios_tools.benchmarks.subjects import SubjectRegistryError, load_subject_registry


ROOT = Path(__file__).resolve().parents[1]
REGISTRY = ROOT / "benchmarks" / "subjects.v0.1.json"
PROFILE_SHA256 = "65a864cc8851945fb19d6051d84f19ca5057cdfea5d2f3a2269acb63507f7e7a"
MODEL_KEY = "gpt-5-mini-2025-08-07-FC"


def _valid_runtime() -> dict[str, object]:
    return {
        "bfcl_root": "/tmp/pinned-bfcl",
        "checkout_present": True,
        "observed_pin": BFCL_PIN,
        "pin_valid": True,
        "worktree_clean": True,
        "model_supported": True,
        "model_handler": "OpenAIResponsesHandler",
        "model_handler_supported": True,
        "validation_error": None,
        "execution_model_valid": True,
    }


@pytest.fixture
def admitted_runtime(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "aios_tools.benchmarks.bfcl_package.inspect_bfcl_checkout",
        lambda **_: _valid_runtime(),
    )


def _case_map(path: Path) -> Path:
    path.write_text(
        json.dumps(
            {
                "simple": ["simple_0"],
                "parallel": ["parallel_0"],
                "multiple": ["multiple_0"],
            }
        )
    )
    return path


def _package(tmp_path: Path):
    return create_bfcl_ab_package(
        registry_path=REGISTRY,
        output_dir=tmp_path / "package",
        case_map_path=_case_map(tmp_path / "cases.json"),
        environ={
            "AIOS_BENCH_BFCL_MODEL": MODEL_KEY,
            "OPENAI_API_KEY": "not-recorded",
            "BFCL_ROOT": "/tmp/pinned-bfcl",
        },
        resource_acknowledged=True,
    )


def test_subject_registry_verifies_profile_and_pair_invariants() -> None:
    registry = load_subject_registry(REGISTRY)
    direct, aios = registry.pair_for("bfcl-v4")
    assert direct.treatment == "DIRECT"
    assert aios.treatment == "AIOS"
    assert direct.model_env == aios.model_env == "AIOS_BENCH_BFCL_MODEL"
    assert aios.verify_profile(registry.repository_root)["profile_hash_valid"] is True


def test_subject_registry_rejects_tampered_profile(tmp_path: Path) -> None:
    root = tmp_path
    (root / "benchmarks" / "profiles").mkdir(parents=True)
    payload = json.loads(REGISTRY.read_text())
    (root / "benchmarks" / "subjects.v0.1.json").write_text(json.dumps(payload))
    (root / "benchmarks" / "profiles" / "aios-master-operator-bfcl.v0.1.txt").write_text(
        "tampered\n"
    )
    with pytest.raises(SubjectRegistryError, match="profile hash"):
        load_subject_registry(root / "benchmarks" / "subjects.v0.1.json")


def test_case_map_parser_rejects_malformed_content(tmp_path: Path) -> None:
    path = tmp_path / "cases.json"
    path.write_text("{}")
    with pytest.raises(BFCLPackageError, match="at least one id"):
        load_case_map(path, ("simple", "parallel", "multiple"))


def test_unresolved_case_shard_cannot_be_ready(
    tmp_path: Path, admitted_runtime: None
) -> None:
    package = create_bfcl_ab_package(
        registry_path=REGISTRY,
        output_dir=tmp_path / "package",
        environ={
            "AIOS_BENCH_BFCL_MODEL": MODEL_KEY,
            "OPENAI_API_KEY": "not-recorded",
            "BFCL_ROOT": "/tmp/pinned-bfcl",
        },
        resource_acknowledged=True,
    )
    manifest = json.loads(package.manifest_path.read_text())
    assert package.status == "BLOCKED"
    assert package.score_status == "NOT_EXECUTED"
    assert manifest["case_shard_status"] == "UNRESOLVED"
    assert manifest["score_status"] == "NOT_EXECUTED"
    assert "not-recorded" not in package.manifest_path.read_text()


def test_resolved_pair_package_is_ready_sealed_and_non_official(
    tmp_path: Path, admitted_runtime: None
) -> None:
    package = _package(tmp_path)
    manifest = json.loads(package.manifest_path.read_text())
    assert package.status == "READY_TO_EXECUTE"
    assert manifest["benchmark_source_ref"] == BFCL_PIN
    assert manifest["run_classification"] == RUN_CLASSIFICATION
    assert manifest["evaluation_scope"] == "OFFICIAL_PARTIAL_EVALUATION"
    assert manifest["official_score_claim_allowed"] is False
    assert manifest["direct_model_key"] == MODEL_KEY
    assert manifest["aios_model_key"] == f"aios::{MODEL_KEY}"
    assert manifest["score_status"] == "NOT_EXECUTED"
    assert manifest["package_file_digests"]
    for relative, expected in manifest["package_file_digests"].items():
        observed = hashlib.sha256((package.output_dir / relative).read_bytes()).hexdigest()
        assert observed == expected
    commands = package.commands_path.read_text()
    assert "status --porcelain=v1 --untracked-files=all" in commands
    assert "verify_package_integrity" in commands
    assert "--partial-eval" in commands
    assert BFCL_PIN in commands
    assert "not-recorded" not in commands


def test_generated_handler_injects_profile_into_actual_first_turn_buffer(
    tmp_path: Path, admitted_runtime: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    package = _package(tmp_path)

    class StubOpenAIResponsesHandler:
        def add_first_turn_message_FC(self, inference_data, first_turn_message):
            inference_data["message"].extend(first_turn_message)
            return inference_data

    modules = {
        "bfcl_eval": types.ModuleType("bfcl_eval"),
        "bfcl_eval.model_handler": types.ModuleType("bfcl_eval.model_handler"),
        "bfcl_eval.model_handler.api_inference": types.ModuleType(
            "bfcl_eval.model_handler.api_inference"
        ),
        "bfcl_eval.model_handler.api_inference.openai_response": types.ModuleType(
            "bfcl_eval.model_handler.api_inference.openai_response"
        ),
    }
    modules[
        "bfcl_eval.model_handler.api_inference.openai_response"
    ].OpenAIResponsesHandler = StubOpenAIResponsesHandler
    for name, module in modules.items():
        monkeypatch.setitem(sys.modules, name, module)

    handler_path = package.output_dir / "overlay" / "aios_bfcl_handler.py"
    spec = importlib.util.spec_from_file_location("generated_aios_handler", handler_path)
    assert spec and spec.loader
    generated = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(generated)
    handler = generated.AIOSOpenAIResponsesHandler()
    original = [{"role": "user", "content": "call the correct tool"}]
    result = handler.add_first_turn_message_FC({"message": []}, original)
    assert original == [{"role": "user", "content": "call the correct tool"}]
    assert result["message"][0] == {
        "role": "developer",
        "content": generated.PROFILE_TEXT,
    }
    assert result["message"][1] == original[0]
    assert sum(
        item.get("content") == generated.PROFILE_TEXT
        for item in result["message"]
    ) == 1


def test_model_validation_is_required_for_admission() -> None:
    registry = load_subject_registry(REGISTRY)
    direct, _ = registry.pair_for("bfcl-v4")
    report = direct.admission(
        repository_root=registry.repository_root,
        environ={
            "AIOS_BENCH_BFCL_MODEL": MODEL_KEY,
            "OPENAI_API_KEY": "present",
        },
        resource_acknowledged=True,
        case_shard_resolved=True,
        model_validation={
            "checkout_present": False,
            "pin_valid": False,
            "worktree_clean": False,
            "model_supported": False,
            "model_handler_supported": False,
            "validation_error": "BFCL_ROOT is not set",
        },
    )
    assert report["execution_admission_ready"] is False
    assert report["model_validation_error"] == "BFCL_ROOT is not set"


def test_comparison_requires_matching_paired_provenance(
    tmp_path: Path, admitted_runtime: None
) -> None:
    package = _package(tmp_path)
    direct_score = tmp_path / "direct.json"
    aios_score = tmp_path / "aios.json"
    direct_score.write_text(json.dumps({"accuracy": 0.5, "tokens": {"input": 100}}))
    aios_score.write_text(json.dumps({"accuracy": 0.75, "tokens": {"input": 120}}))
    result = compare_score_artifacts(
        direct_path=direct_score,
        aios_path=aios_score,
        direct_manifest_path=package.direct_manifest_path,
        aios_manifest_path=package.aios_manifest_path,
    )
    metrics = {item["metric"]: item for item in result["metrics"]}
    assert metrics["accuracy"]["delta"] == pytest.approx(0.25)
    assert result["package_id"]
    assert result["case_map_sha256"]
    assert result["official_score_claim_allowed"] is False
    assert result["raw_artifacts_authoritative"] is True
    assert result["comparison_authoritative"] is False


def test_comparison_rejects_different_case_shards(
    tmp_path: Path, admitted_runtime: None
) -> None:
    package = _package(tmp_path)
    altered = json.loads(package.aios_manifest_path.read_text())
    altered["case_map_sha256"] = "0" * 64
    package.aios_manifest_path.write_text(json.dumps(altered))
    direct_score = tmp_path / "direct.json"
    aios_score = tmp_path / "aios.json"
    direct_score.write_text(json.dumps({"accuracy": 0.5}))
    aios_score.write_text(json.dumps({"accuracy": 0.75}))
    with pytest.raises(ScoreComparisonError, match="case_map_sha256"):
        compare_score_artifacts(
            direct_path=direct_score,
            aios_path=aios_score,
            direct_manifest_path=package.direct_manifest_path,
            aios_manifest_path=package.aios_manifest_path,
        )


def test_unresolved_package_runner_fails_closed(tmp_path: Path) -> None:
    package = create_bfcl_ab_package(
        registry_path=REGISTRY,
        output_dir=tmp_path / "package",
        environ={},
        resource_acknowledged=False,
    )
    commands = package.commands_path.read_text()
    assert "BLOCKED: resolve the BFCL case shard first." in commands
    assert "AIOS_BENCH_ACK_RESOURCE=bfcl-v4" in commands
    assert package.status == "BLOCKED"


def test_generated_overlay_and_runner_are_syntactically_valid(
    tmp_path: Path, admitted_runtime: None
) -> None:
    import py_compile
    import subprocess

    package = _package(tmp_path)
    py_compile.compile(
        str(package.output_dir / "overlay" / "aios_bfcl_handler.py"),
        doraise=True,
    )
    py_compile.compile(
        str(package.output_dir / "overlay" / "sitecustomize.py"),
        doraise=True,
    )
    subprocess.run(["bash", "-n", str(package.commands_path)], check=True)
