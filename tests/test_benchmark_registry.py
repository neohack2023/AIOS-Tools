from pathlib import Path

from aios_tools.benchmarks.registry import load_benchmark_registry


def test_registry_loads_unique_official_sources() -> None:
    registry = load_benchmark_registry(Path("benchmarks/registry.v0.1.json"))
    assert registry.version == "0.1.0"
    assert len(registry.benchmarks) == len({item.id for item in registry.benchmarks})
    assert all(item.source_url.startswith("https://github.com/") for item in registry.benchmarks)


def test_unpinned_sources_cannot_claim_official_readiness() -> None:
    registry = load_benchmark_registry(Path("benchmarks/registry.v0.1.json"))
    assert registry.benchmarks
    assert all(not item.is_immutably_pinned for item in registry.benchmarks)


def test_required_classifications_are_registered() -> None:
    registry = load_benchmark_registry(Path("benchmarks/registry.v0.1.json"))
    assert set(registry.classifications) == {
        "OFFICIAL_FULL_RUN",
        "PROTOCOL_SMOKE",
        "STANDARDS_CONFORMANCE",
        "HUMAN_REVIEW",
    }
