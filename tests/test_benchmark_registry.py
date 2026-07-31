from pathlib import Path

from aios_tools.benchmarks.registry import load_benchmark_registry


def test_registry_loads_unique_official_sources() -> None:
    registry = load_benchmark_registry(Path("benchmarks/registry.v0.1.json"))
    assert registry.version == "0.2.0"
    assert len(registry.benchmarks) == len({item.id for item in registry.benchmarks})
    assert all(item.source_url.startswith("https://github.com/") for item in registry.benchmarks)
    assert all(item.pin_ready for item in registry.benchmarks)


def test_official_readiness_is_classification_aware() -> None:
    registry = load_benchmark_registry(Path("benchmarks/registry.v0.1.json"))
    official = [item for item in registry.benchmarks if item.classification == "OFFICIAL_FULL_RUN"]
    standards = registry.by_id("json-schema-2020-12")
    assert official
    assert all(item.official_ready for item in official)
    assert standards.pin_ready is True
    assert standards.official_ready is False
    assert standards.classification == "STANDARDS_CONFORMANCE"


def test_required_classifications_are_registered() -> None:
    registry = load_benchmark_registry(Path("benchmarks/registry.v0.1.json"))
    assert set(registry.classifications) == {
        "OFFICIAL_FULL_RUN",
        "PROTOCOL_SMOKE",
        "STANDARDS_CONFORMANCE",
        "HUMAN_REVIEW",
    }


def test_all_registry_commands_are_executable_contracts() -> None:
    registry = load_benchmark_registry(Path("benchmarks/registry.v0.1.json"))
    assert all(item.prepare for item in registry.benchmarks)
    assert all(item.gold_check for item in registry.benchmarks)
    assert all(not command.startswith("run ") for item in registry.benchmarks for command in (*item.prepare, item.gold_check))
