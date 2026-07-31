from pathlib import Path

from aios_tools.benchmarks.plan import build_execution_plan
from aios_tools.benchmarks.registry import load_benchmark_registry


def test_first_wave_registry_is_immutably_pinned() -> None:
    registry = load_benchmark_registry()
    assert registry.version == "0.2.0"
    assert len(registry.benchmarks) == 6
    assert all(item.official_ready for item in registry.benchmarks)
    assert all(item.gold_check for item in registry.benchmarks)


def test_execution_plan_checks_out_detached_commit() -> None:
    benchmark = load_benchmark_registry().by_id("agentdojo")
    plan = build_execution_plan(benchmark, workspace_root=Path("work"))
    assert plan.classification == "OFFICIAL_FULL_RUN"
    assert plan.workspace.endswith(benchmark.source_ref[:12])
    assert plan.prepare[1] == f"git -C {plan.workspace} checkout --detach {benchmark.source_ref}"
    assert plan.gold_check == benchmark.gold_check
