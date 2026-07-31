from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path

from .registry import BenchmarkDefinition


@dataclass(frozen=True)
class BenchmarkExecutionPlan:
    benchmark_id: str
    classification: str
    source_url: str
    source_ref: str
    workspace: str
    prepare: tuple[str, ...]
    gold_check: str
    result_glob: str
    required_secrets: tuple[str, ...]
    resource_class: str

    def to_json(self) -> str:
        return json.dumps(asdict(self), indent=2, sort_keys=True)


def build_execution_plan(
    benchmark: BenchmarkDefinition,
    *,
    workspace_root: Path = Path(".benchmark-workspaces"),
) -> BenchmarkExecutionPlan:
    if not benchmark.official_ready:
        raise ValueError(f"benchmark {benchmark.id} is not immutably pinned")
    workspace = workspace_root / f"{benchmark.id}-{benchmark.source_ref[:12]}"
    return BenchmarkExecutionPlan(
        benchmark_id=benchmark.id,
        classification="OFFICIAL_FULL_RUN",
        source_url=benchmark.source_url,
        source_ref=benchmark.source_ref,
        workspace=str(workspace),
        prepare=(
            f"git clone {benchmark.source_url} {workspace}",
            f"git -C {workspace} checkout --detach {benchmark.source_ref}",
            *benchmark.prepare,
        ),
        gold_check=benchmark.gold_check,
        result_glob=benchmark.official_result_glob,
        required_secrets=benchmark.secrets,
        resource_class=benchmark.resource_class,
    )


def write_execution_plan(plan: BenchmarkExecutionPlan, output: Path) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(plan.to_json() + "\n", encoding="utf-8")
