from __future__ import annotations

import json
import zipfile
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]

from aios_tools.package_eval import (
    PortablePackageEvalError,
    build_eval_capsule,
    execute_openai_pair,
)


def _fixture(path: Path) -> Path:
    payload = {
        "fixture_version": "0.1",
        "fixture_id": "acceptance-integrity-01",
        "task_prompt": "Return the requested structured result.",
        "package_entry_instruction": "Use the attached package working knowledge.",
        "allowed_tools": [],
        "semantic_dimensions": ["instruction_following"],
        "deterministic_assertions": {
            "required_markers": ["RESULT"],
        },
        "product_surface": {
            "required": False,
            "lane": "NONE",
            "human_takeover_allowed": False,
        },
    }
    path.write_text(json.dumps(payload), encoding="utf-8")
    return path


def _package(path: Path) -> Path:
    with zipfile.ZipFile(path, "w") as archive:
        archive.writestr("SKILL.md", "# Test Skill\nEmit RESULT.")
    return path


def _completed_response(*, response_id: str, text: str) -> dict[str, object]:
    return {
        "id": response_id,
        "status": "completed",
        "output": [{
            "type": "message",
            "content": [{"type": "output_text", "text": text}],
        }],
    }


def test_pair_execution_rejects_tampered_capsule_artifact_before_transport(
    tmp_path: Path,
) -> None:
    package = _package(tmp_path / "tool.zip")
    capsule = build_eval_capsule(
        package_path=package,
        fixture_path=_fixture(tmp_path / "fixture.json"),
        output_dir=tmp_path / "capsule",
    )

    request_path = capsule.package_on_path
    request = json.loads(request_path.read_text(encoding="utf-8"))
    request["task_prompt"] = "tampered after capsule creation"
    request_path.write_text(json.dumps(request), encoding="utf-8")

    calls = 0

    def transport(**kwargs):
        nonlocal calls
        calls += 1
        raise AssertionError("transport must not run for a stale capsule")

    with pytest.raises(
        PortablePackageEvalError,
        match=r"capsule artifact digest mismatch: package-on-request\.json",
    ):
        execute_openai_pair(
            capsule_dir=capsule.output_dir,
            package_path=package,
            model="test-model",
            api_key="secret-test-key",
            output_dir=tmp_path / "results",
            transport=transport,
        )
    assert calls == 0


def test_pair_execution_rejects_non_completed_response_before_second_treatment(
    tmp_path: Path,
) -> None:
    package = _package(tmp_path / "tool.zip")
    capsule = build_eval_capsule(
        package_path=package,
        fixture_path=_fixture(tmp_path / "fixture.json"),
        output_dir=tmp_path / "capsule",
    )

    calls = 0

    def transport(**kwargs):
        nonlocal calls
        calls += 1
        return {
            "id": "resp-failed",
            "status": "failed",
            "output": [{
                "type": "message",
                "content": [{"type": "output_text", "text": "RESULT but failed"}],
            }],
        }

    with pytest.raises(
        PortablePackageEvalError,
        match="PACKAGE_OFF response status must be completed",
    ):
        execute_openai_pair(
            capsule_dir=capsule.output_dir,
            package_path=package,
            model="test-model",
            api_key="secret-test-key",
            output_dir=tmp_path / "results",
            transport=transport,
        )
    assert calls == 1


def test_pair_execution_rejects_replayed_response_identity(tmp_path: Path) -> None:
    package = _package(tmp_path / "tool.zip")
    capsule = build_eval_capsule(
        package_path=package,
        fixture_path=_fixture(tmp_path / "fixture.json"),
        output_dir=tmp_path / "capsule",
    )

    calls = 0

    def transport(**kwargs):
        nonlocal calls
        calls += 1
        text = "baseline" if calls == 1 else "RESULT"
        return _completed_response(response_id="resp-replayed", text=text)

    with pytest.raises(
        PortablePackageEvalError,
        match="paired Responses run must produce distinct response ids",
    ):
        execute_openai_pair(
            capsule_dir=capsule.output_dir,
            package_path=package,
            model="test-model",
            api_key="secret-test-key",
            output_dir=tmp_path / "results",
            transport=transport,
        )
    assert calls == 2


def test_acceptance_integrity_anti_pattern_fixture_binds_regressions() -> None:
    mapping_path = (
        ROOT
        / "fixtures"
        / "package-eval"
        / "portable-package-eval-acceptance-integrity-01.json"
    )
    payload = json.loads(mapping_path.read_text(encoding="utf-8"))
    assert payload["anti_pattern_id"] == "PORTABLE_PACKAGE_EVAL_ACCEPTANCE_INTEGRITY_01"
    assert payload["status"] == "CONFIRMED_ANTI_PATTERN"
    assert payload["source_test_file"] == (
        "tests/test_portable_package_eval_acceptance_integrity.py"
    )

    seen: set[str] = set()
    for pattern in payload["patterns"]:
        assert pattern["id"] not in seen
        seen.add(pattern["id"])
        assert pattern["regression_tests"]
        for test_name in pattern["regression_tests"]:
            candidate = globals().get(test_name)
            assert callable(candidate), f"anti-pattern regression missing: {test_name}"

    assert seen == {"AP-05", "AP-06", "AP-07"}
    assert payload["acceptance_effect"]["authority_transfer"] is False
