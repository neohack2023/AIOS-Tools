from __future__ import annotations

import argparse
import json
import shutil
from pathlib import Path

from .registry import BenchmarkRegistryError, load_benchmark_registry


def _doctor_item(benchmark: object) -> dict[str, object]:
    runtime = getattr(benchmark, "runtime")
    executable = {"python": "python", "conda": "conda", "uv": "uv", "docker": "docker"}.get(runtime, runtime)
    return {
        "id": getattr(benchmark, "id"),
        "name": getattr(benchmark, "name"),
        "runtime": runtime,
        "runtime_available": shutil.which(executable) is not None,
        "source_ref": getattr(benchmark, "source_ref"),
        "immutably_pinned": getattr(benchmark, "is_immutably_pinned"),
        "official_run_ready": shutil.which(executable) is not None and getattr(benchmark, "is_immutably_pinned"),
        "resource_class": getattr(benchmark, "resource_class"),
        "required_secrets": list(getattr(benchmark, "secrets")),
    }


def main() -> None:
    parser = argparse.ArgumentParser(prog="aios-bench")
    parser.add_argument("--registry", type=Path, default=Path("benchmarks/registry.v0.1.json"))
    subparsers = parser.add_subparsers(dest="command", required=True)
    subparsers.add_parser("list")
    doctor = subparsers.add_parser("doctor")
    doctor.add_argument("benchmark_id", nargs="?")
    args = parser.parse_args()
    try:
        registry = load_benchmark_registry(args.registry)
    except BenchmarkRegistryError as exc:
        print(json.dumps({"status": "BLOCKED", "error": str(exc)}, indent=2))
        raise SystemExit(1) from exc
    if args.command == "list":
        print(json.dumps({"registry_version": registry.version, "benchmarks": [item.id for item in registry.benchmarks]}, indent=2))
        return
    items = registry.benchmarks
    if args.benchmark_id:
        try:
            items = (registry.by_id(args.benchmark_id),)
        except KeyError as exc:
            print(json.dumps({"status": "BLOCKED", "error": f"unknown benchmark: {args.benchmark_id}"}, indent=2))
            raise SystemExit(2) from exc
    report = [_doctor_item(item) for item in items]
    ready = all(bool(item["official_run_ready"]) for item in report)
    print(json.dumps({"status": "READY" if ready else "BLOCKED", "registry_version": registry.version, "benchmarks": report}, indent=2))
    raise SystemExit(0 if ready else 1)


if __name__ == "__main__":
    main()
