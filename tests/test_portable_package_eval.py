from __future__ import annotations

import json
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator

from aios_tools.package_eval import (
    PortablePackageEvalError,
    build_eval_capsule,
    compare_grade_results,
    grade_output_text,
)


ROOT = Path(__file__).resolve().parents[1]


def _fixture(path: Path, *, required_surface: bool = True) -> Path:
    payload = {
        "fixture_version": "0.1",
        "fixture_id": "portable-eval-fixture-01",
        "task_prompt": "Build the requested artifact and return the required sections.",
        "package_entry_instruction": "Use only the attached package as package-specific context.",
        "allowed_tools": ["web_search"],
        "semantic_dimensions": ["instruction_following", "format_fidelity"],
        "deterministic_assertions": {
            "required_markers": ["STYLE PROMPT", "LYRICS"],
            "forbidden_markers": ["I can also"],
            "ordered_markers": ["STYLE PROMPT", "LYRICS"],
            "required_regex": [r"(?m)^STYLE PROMPT$"],
            "max_total_chars": 2000,
        },
        "product_surface": {
            "required": required_surface,
            "lane": (
                "CHATGPT_TEMPORARY_UNPERSONALIZED"
                if required_surface
                else "NONE"
            ),
            "human_takeover_allowed": True,
        },
    }
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return path


def test_capsule_is_clean_room_paired_and_schema_valid(tmp_path: Path) -> None:
    package = tmp_path / "tool.zip"
    package.write_bytes(b"portable-package-fixture")
    fixture = _fixture(tmp_path / "fixture.json")
    capsule = build_eval_capsule(
        package_path=package,
        fixture_path=fixture,
        output_dir=tmp_path / "capsule",
    )
    manifest = json.loads(capsule.manifest_path.read_text(encoding="utf-8"))
    schema = json.loads(
        (ROOT / "contracts/portable-package-eval-manifest.v0.1.schema.json").read_text(
            encoding="utf-8"
        )
    )
    Draft202012Validator(schema).validate(manifest)
    assert capsule.status == "READY_TO_EXECUTE"
    assert manifest["score_status"] == "NOT_EXECUTED"
    assert manifest["product_surface_status"] == "NOT_EXECUTED"
    assert manifest["run_classification"] == "PORTABLE_PACKAGE_REGRESSION"

    on = json.loads(capsule.package_on_path.read_text(encoding="utf-8"))
    off = json.loads(capsule.package_off_path.read_text(encoding="utf-8"))
    for field in manifest["pairing"]["invariant_fields"]:
        assert on[field] == off[field]
    assert on["package_attachment"]["sha256"] == capsule.package_sha256
    assert off["package_attachment"] is None
    assert on["clean_room"]["memory"] is False
    assert on["clean_room"]["project_context"] is False
    assert on["clean_room"]["custom_instructions"] is False
    assert on["store"] is False


def test_product_surface_plan_requires_unpersonalized_and_takeover_blackout(
    tmp_path: Path,
) -> None:
    package = tmp_path / "tool.zip"
    package.write_bytes(b"artifact")
    capsule = build_eval_capsule(
        package_path=package,
        fixture_path=_fixture(tmp_path / "fixture.json"),
        output_dir=tmp_path / "capsule",
    )
    plan = json.loads(capsule.product_surface_plan_path.read_text(encoding="utf-8"))
    assert plan["lane"] == "CHATGPT_TEMPORARY_UNPERSONALIZED"
    assert plan["status"] == "NOT_EXECUTED"
    assert plan["temporary_chat"]["personalization"] == "UNPERSONALIZED"
    assert plan["temporary_chat"]["plugins"] is False
    assert plan["human_takeover"]["allowed"] is True
    assert plan["human_takeover"]["secret_input_model_visible"] is False
    assert plan["human_takeover"]["states"][-1] == "AUTOMATION_RESUMED"


def test_deterministic_grader_and_pair_comparison() -> None:
    grader = {
        "deterministic_assertions": {
            "required_markers": ["STYLE PROMPT", "LYRICS"],
            "forbidden_markers": ["I can also"],
            "ordered_markers": ["STYLE PROMPT", "LYRICS"],
            "required_regex": [r"(?m)^STYLE PROMPT$"],
            "max_total_chars": 500,
        }
    }
    package_off = grade_output_text(
        output_text="STYLE PROMPT\nplain answer",
        grader_contract=grader,
    )
    package_on = grade_output_text(
        output_text="STYLE PROMPT\nproducer text\nLYRICS\nbar one",
        grader_contract=grader,
    )
    comparison = compare_grade_results(
        package_off=package_off,
        package_on=package_on,
    )
    assert package_off["deterministic_status"] == "FAIL"
    assert package_on["deterministic_status"] == "PASS"
    assert comparison["passed_check_delta"] > 0
    assert comparison["comparison_authoritative"] is False
    assert comparison["semantic_comparison_status"] == "NOT_EXECUTED"


def test_required_product_surface_cannot_use_none_lane(tmp_path: Path) -> None:
    package = tmp_path / "tool.zip"
    package.write_bytes(b"artifact")
    fixture = json.loads(_fixture(tmp_path / "fixture.json").read_text())
    fixture["product_surface"]["lane"] = "NONE"
    path = tmp_path / "bad.json"
    path.write_text(json.dumps(fixture), encoding="utf-8")
    with pytest.raises(PortablePackageEvalError, match="must declare a real lane"):
        build_eval_capsule(
            package_path=package,
            fixture_path=path,
            output_dir=tmp_path / "capsule",
        )


def test_fixture_schema_accepts_reference_fixture(tmp_path: Path) -> None:
    fixture_path = _fixture(tmp_path / "fixture.json")
    payload = json.loads(fixture_path.read_text(encoding="utf-8"))
    schema = json.loads(
        (ROOT / "contracts/portable-package-eval-fixture.v0.1.schema.json").read_text(
            encoding="utf-8"
        )
    )
    Draft202012Validator(schema).validate(payload)
