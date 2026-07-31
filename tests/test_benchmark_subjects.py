from __future__ import annotations

import json
from pathlib import Path

import pytest

from aios_tools.benchmarks.bfcl_package import BFCL_PIN, create_bfcl_ab_package
from aios_tools.benchmarks.compare import compare_score_artifacts
from aios_tools.benchmarks.subjects import SubjectRegistryError, load_subject_registry


ROOT = Path(__file__).resolve().parents[1]
REGISTRY = ROOT / "benchmarks" / "subjects.v0.1.json"


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
    (root / "benchmarks" / "subjects.v0.1.json").write_text(
        json.dumps(payload)
    )
    (root / "benchmarks" / "profiles" / "aios-master-operator-bfcl.v0.1.txt").write_text(
        "tampered\n"
    )
    with pytest.raises(SubjectRegistryError, match="profile hash"):
        load_subject_registry(root / "benchmarks" / "subjects.v0.1.json")


def test_unresolved_case_shard_cannot_be_ready(tmp_path: Path) -> None:
    package = create_bfcl_ab_package(
        registry_path=REGISTRY,
        output_dir=tmp_path / "package",
        environ={
            "AIOS_BENCH_BFCL_MODEL": "gpt-5-mini-2025-08-07-FC",
            "OPENAI_API_KEY": "not-recorded",
        },
        resource_acknowledged=True,
    )
    manifest = json.loads(package.manifest_path.read_text())
    assert package.status == "BLOCKED"
    assert package.score_status == "NOT_EXECUTED"
    assert manifest["case_shard_status"] == "UNRESOLVED"
    assert manifest["score_status"] == "NOT_EXECUTED"
    assert "not-recorded" not in package.manifest_path.read_text()


def test_resolved_pair_package_is_ready_but_not_scored(tmp_path: Path) -> None:
    case_map = tmp_path / "cases.json"
    case_map.write_text(
        json.dumps(
            {
                "simple": ["simple_0"],
                "parallel": ["parallel_0"],
                "multiple": ["multiple_0"],
            }
        )
    )
    package = create_bfcl_ab_package(
        registry_path=REGISTRY,
        output_dir=tmp_path / "package",
        case_map_path=case_map,
        environ={
            "AIOS_BENCH_BFCL_MODEL": "gpt-5-mini-2025-08-07-FC",
            "OPENAI_API_KEY": "not-recorded",
        },
        resource_acknowledged=True,
    )
    manifest = json.loads(package.manifest_path.read_text())
    assert package.status == "READY_TO_EXECUTE"
    assert manifest["benchmark_source_ref"] == BFCL_PIN
    assert manifest["direct_model_key"] == "gpt-5-mini-2025-08-07-FC"
    assert manifest["aios_model_key"] == "aios::gpt-5-mini-2025-08-07-FC"
    assert manifest["score_status"] == "NOT_EXECUTED"
    assert (package.output_dir / "overlay" / "sitecustomize.py").is_file()
    handler = (package.output_dir / "overlay" / "aios_bfcl_handler.py").read_text()
    assert "AIOS-OPERATOR-001-BFCL-v0.1" in handler
    commands = package.commands_path.read_text()
    assert "--partial-eval" in commands
    assert BFCL_PIN in commands
    assert "not-recorded" not in commands
    assert 'DIRECT_MODEL_KEY="$AIOS_BENCH_BFCL_MODEL"' in commands
    assert "AIOS_BENCH_ACK_RESOURCE" in commands
    assert "BLOCKED: resolve the BFCL case shard first." not in commands


def test_comparison_preserves_raw_artifact_authority(tmp_path: Path) -> None:
    direct = tmp_path / "direct.json"
    aios = tmp_path / "aios.json"
    direct.write_text(json.dumps({"accuracy": 0.5, "tokens": {"input": 100}}))
    aios.write_text(json.dumps({"accuracy": 0.75, "tokens": {"input": 120}}))
    result = compare_score_artifacts(
        direct_path=direct,
        aios_path=aios,
        benchmark_source_ref=BFCL_PIN,
        profile_sha256="65a864cc8851945fb19d6051d84f19ca5057cdfea5d2f3a2269acb63507f7e7a",
    )
    metrics = {item["metric"]: item for item in result["metrics"]}
    assert metrics["accuracy"]["delta"] == pytest.approx(0.25)
    assert result["raw_artifacts_authoritative"] is True
    assert result["comparison_authoritative"] is False


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


def test_generated_overlay_and_runner_are_syntactically_valid(tmp_path: Path) -> None:
    import py_compile
    import subprocess

    case_map = tmp_path / "cases.json"
    case_map.write_text(
        json.dumps(
            {
                "simple": ["simple_0"],
                "parallel": ["parallel_0"],
                "multiple": ["multiple_0"],
            }
        )
    )
    package = create_bfcl_ab_package(
        registry_path=REGISTRY,
        output_dir=tmp_path / "package",
        case_map_path=case_map,
        environ={
            "AIOS_BENCH_BFCL_MODEL": "gpt-5-mini-2025-08-07-FC",
            "OPENAI_API_KEY": "not-recorded",
        },
        resource_acknowledged=True,
    )
    py_compile.compile(
        str(package.output_dir / "overlay" / "aios_bfcl_handler.py"),
        doraise=True,
    )
    py_compile.compile(
        str(package.output_dir / "overlay" / "sitecustomize.py"),
        doraise=True,
    )
    subprocess.run(["bash", "-n", str(package.commands_path)], check=True)
