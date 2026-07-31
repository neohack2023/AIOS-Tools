import json
from pathlib import Path

from aios_tools.benchmarks.cli import _doctor_item
from aios_tools.benchmarks.json_schema_adapter import run_case
from aios_tools.benchmarks.plan import build_execution_plan
from aios_tools.benchmarks.registry import load_benchmark_registry


def test_first_wave_registry_is_immutably_pinned() -> None:
    registry = load_benchmark_registry()
    assert registry.version == "0.2.0"
    assert len(registry.benchmarks) == 6
    assert all(item.pin_ready for item in registry.benchmarks)
    assert all(item.gold_check for item in registry.benchmarks)
    assert registry.by_id("json-schema-2020-12").classification == "STANDARDS_CONFORMANCE"


def test_execution_plan_checks_out_detached_commit_and_preserves_classification() -> None:
    benchmark = load_benchmark_registry().by_id("json-schema-2020-12")
    plan = build_execution_plan(benchmark, workspace_root=Path("work"))
    assert plan.classification == "STANDARDS_CONFORMANCE"
    assert plan.workspace.endswith(benchmark.source_ref[:12])
    assert plan.prepare[1] == f"git -C {plan.workspace} checkout --detach {benchmark.source_ref}"
    assert plan.gold_check == benchmark.gold_check
    assert "resource_class_acknowledged" in plan.admission_requirements


def test_doctor_requires_secrets_and_resource_acknowledgement(monkeypatch) -> None:
    benchmark = load_benchmark_registry().by_id("agentdojo")
    monkeypatch.setattr("aios_tools.benchmarks.cli.shutil.which", lambda _: "/usr/bin/tool")
    blocked = _doctor_item(benchmark, acknowledged_resources=set(), environ={})
    assert blocked["pin_ready"] is True
    assert blocked["execution_admission_ready"] is False
    assert blocked["missing_secrets"] == ["OPENAI_API_KEY"]
    ready = _doctor_item(
        benchmark,
        acknowledged_resources={"agentdojo"},
        environ={"OPENAI_API_KEY": "test-only"},
    )
    assert ready["execution_admission_ready"] is True
    assert ready["score_status"] == "NOT_EXECUTED"


def test_json_schema_adapter_executes_required_case(tmp_path: Path) -> None:
    suite_file = tmp_path / "tests" / "draft2020-12" / "type.json"
    suite_file.parent.mkdir(parents=True)
    suite_file.write_text(
        json.dumps(
            [
                {
                    "description": "integer type",
                    "schema": {"type": "integer"},
                    "tests": [
                        {"description": "integer passes", "data": 1, "valid": True},
                        {"description": "string fails", "data": "1", "valid": False},
                    ],
                }
            ]
        ),
        encoding="utf-8",
    )
    result = run_case(
        suite_root=tmp_path,
        relative_file=Path("tests/draft2020-12/type.json"),
        case_index=0,
    )
    assert result["classification"] == "STANDARDS_CONFORMANCE"
    assert result["passed"] is True
