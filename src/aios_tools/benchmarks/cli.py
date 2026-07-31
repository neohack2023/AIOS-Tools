from __future__ import annotations

import argparse
import json
import os
import shutil
from collections.abc import Mapping
from pathlib import Path

from .registry import BenchmarkRegistryError, load_benchmark_registry


def _doctor_item(
    benchmark: object,
    *,
    acknowledged_resources: set[str],
    environ: Mapping[str, str] | None = None,
) -> dict[str, object]:
    environment = os.environ if environ is None else environ
    runtime = getattr(benchmark, "runtime")
    executable = {"python": "python", "conda": "conda", "uv": "uv", "docker": "docker"}.get(runtime, runtime)
    required_secrets = tuple(getattr(benchmark, "secrets"))
    missing_secrets = [name for name in required_secrets if not environment.get(name)]
    resource_acknowledged = getattr(benchmark, "id") in acknowledged_resources or "all" in acknowledged_resources
    runtime_available = shutil.which(executable) is not None
    pin_ready = bool(getattr(benchmark, "pin_ready"))
    gold_check_command_valid = bool(getattr(benchmark, "gold_check"))
    execution_admission_ready = all(
        (
            pin_ready,
            runtime_available,
            not missing_secrets,
            resource_acknowledged,
            gold_check_command_valid,
        )
    )
    return {
        "id": getattr(benchmark, "id"),
        "name": getattr(benchmark, "name"),
        "classification": getattr(benchmark, "classification"),
        "runtime": runtime,
        "runtime_available": runtime_available,
        "python": getattr(benchmark, "python"),
        "source_ref": getattr(benchmark, "source_ref"),
        "source_ref_policy": getattr(benchmark, "source_ref_policy"),
        "pin_ready": pin_ready,
        "gold_check_command_valid": gold_check_command_valid,
        "resource_class": getattr(benchmark, "resource_class"),
        "resource_acknowledged": resource_acknowledged,
        "required_secrets": list(required_secrets),
        "missing_secrets": missing_secrets,
        "execution_admission_ready": execution_admission_ready,
        "score_status": "NOT_EXECUTED",
    }


def main() -> None:
    parser = argparse.ArgumentParser(prog="aios-bench")
    parser.add_argument("--registry", type=Path, default=Path("benchmarks/registry.v0.1.json"))
    subparsers = parser.add_subparsers(dest="command", required=True)
    subparsers.add_parser("list")
    doctor = subparsers.add_parser("doctor")
    doctor.add_argument("benchmark_id", nargs="?")
    doctor.add_argument(
        "--ack-resource",
        action="append",
        default=[],
        metavar="BENCHMARK_ID",
        help="Acknowledge the declared resource class for one benchmark; use 'all' only for an intentional full-registry check.",
    )
    args = parser.parse_args()
    try:
        registry = load_benchmark_registry(args.registry)
    except BenchmarkRegistryError as exc:
        print(json.dumps({"status": "BLOCKED", "error": str(exc)}, indent=2))
        raise SystemExit(1) from exc
    if args.command == "list":
        print(
            json.dumps(
                {
                    "registry_version": registry.version,
                    "benchmarks": [
                        {"id": item.id, "classification": item.classification, "pin_ready": item.pin_ready}
                        for item in registry.benchmarks
                    ],
                },
                indent=2,
            )
        )
        return
    items = registry.benchmarks
    if args.benchmark_id:
        try:
            items = (registry.by_id(args.benchmark_id),)
        except KeyError as exc:
            print(json.dumps({"status": "BLOCKED", "error": f"unknown benchmark: {args.benchmark_id}"}, indent=2))
            raise SystemExit(2) from exc
    acknowledgements = set(args.ack_resource)
    unknown_acknowledgements = acknowledgements - {item.id for item in registry.benchmarks} - {"all"}
    if unknown_acknowledgements:
        print(
            json.dumps(
                {"status": "BLOCKED", "error": f"unknown resource acknowledgement: {sorted(unknown_acknowledgements)}"},
                indent=2,
            )
        )
        raise SystemExit(2)
    report = [_doctor_item(item, acknowledged_resources=acknowledgements) for item in items]
    ready = all(bool(item["execution_admission_ready"]) for item in report)
    print(
        json.dumps(
            {
                "status": "READY_TO_EXECUTE" if ready else "BLOCKED",
                "registry_version": registry.version,
                "benchmarks": report,
                "score_status": "NOT_EXECUTED",
            },
            indent=2,
        )
    )
    raise SystemExit(0 if ready else 1)


if __name__ == "__main__":
    main()
