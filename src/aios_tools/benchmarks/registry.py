from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any


class BenchmarkRegistryError(ValueError):
    """Raised when the benchmark registry is malformed or unsafe."""


@dataclass(frozen=True)
class BenchmarkDefinition:
    id: str
    name: str
    source_url: str
    source_ref: str
    source_ref_policy: str
    runtime: str
    capabilities: tuple[str, ...]
    prepare: tuple[str, ...]
    gold_check: str
    official_result_glob: str
    secrets: tuple[str, ...]
    resource_class: str

    @property
    def is_immutably_pinned(self) -> bool:
        ref = self.source_ref.lower()
        return len(ref) == 40 and all(char in "0123456789abcdef" for char in ref)

    @property
    def official_ready(self) -> bool:
        return self.source_ref_policy == "IMMUTABLE_COMMIT" and self.is_immutably_pinned


@dataclass(frozen=True)
class BenchmarkRegistry:
    version: str
    classifications: tuple[str, ...]
    benchmarks: tuple[BenchmarkDefinition, ...]

    def by_id(self, benchmark_id: str) -> BenchmarkDefinition:
        for benchmark in self.benchmarks:
            if benchmark.id == benchmark_id:
                return benchmark
        raise KeyError(benchmark_id)


def _require_text(item: dict[str, Any], key: str) -> str:
    value = item.get(key)
    if not isinstance(value, str) or not value.strip():
        raise BenchmarkRegistryError(f"benchmark field {key!r} must be non-empty text")
    return value


def _require_text_list(item: dict[str, Any], key: str) -> tuple[str, ...]:
    value = item.get(key)
    if not isinstance(value, list) or any(not isinstance(entry, str) or not entry for entry in value):
        raise BenchmarkRegistryError(f"benchmark field {key!r} must be a list of text values")
    return tuple(value)


def load_benchmark_registry(path: Path | None = None) -> BenchmarkRegistry:
    registry_path = path or Path("benchmarks/registry.v0.1.json")
    try:
        raw = json.loads(registry_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise BenchmarkRegistryError(f"unable to load benchmark registry: {exc}") from exc
    if not isinstance(raw, dict):
        raise BenchmarkRegistryError("benchmark registry root must be an object")
    version = _require_text(raw, "registry_version")
    classifications = _require_text_list(raw, "classification_values")
    items = raw.get("benchmarks")
    if not isinstance(items, list) or not items:
        raise BenchmarkRegistryError("benchmarks must be a non-empty list")
    definitions: list[BenchmarkDefinition] = []
    seen: set[str] = set()
    for item in items:
        if not isinstance(item, dict):
            raise BenchmarkRegistryError("each benchmark must be an object")
        benchmark_id = _require_text(item, "id")
        if benchmark_id in seen:
            raise BenchmarkRegistryError(f"duplicate benchmark id: {benchmark_id}")
        seen.add(benchmark_id)
        source_url = _require_text(item, "source_url")
        if not source_url.startswith("https://github.com/"):
            raise BenchmarkRegistryError(f"benchmark {benchmark_id} must use an official GitHub source URL")
        definition = BenchmarkDefinition(
            id=benchmark_id,
            name=_require_text(item, "name"),
            source_url=source_url,
            source_ref=_require_text(item, "source_ref"),
            source_ref_policy=_require_text(item, "source_ref_policy"),
            runtime=_require_text(item, "runtime"),
            capabilities=_require_text_list(item, "capabilities"),
            prepare=_require_text_list(item, "prepare"),
            gold_check=_require_text(item, "gold_check"),
            official_result_glob=_require_text(item, "official_result_glob"),
            secrets=_require_text_list(item, "secrets"),
            resource_class=_require_text(item, "resource_class"),
        )
        if definition.source_ref_policy == "IMMUTABLE_COMMIT" and not definition.is_immutably_pinned:
            raise BenchmarkRegistryError(f"benchmark {benchmark_id} declares IMMUTABLE_COMMIT without a 40-character SHA")
        definitions.append(definition)
    return BenchmarkRegistry(version, classifications, tuple(definitions))
