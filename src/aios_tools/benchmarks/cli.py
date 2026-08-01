from __future__ import annotations

import argparse
import json
import os
import shutil
from collections.abc import Mapping
from pathlib import Path

from .bfcl_package import (
    DEFAULT_CATEGORIES,
    BFCLPackageError,
    create_bfcl_ab_package,
    ensure_categories,
    inspect_bfcl_checkout,
    load_case_map,
)
from .compare import ScoreComparisonError, compare_score_artifacts
from .registry import BenchmarkRegistryError, load_benchmark_registry
from .subjects import SubjectRegistryError, load_subject_registry


def _doctor_item(
    benchmark: object,
    *,
    acknowledged_resources: set[str],
    environ: Mapping[str, str] | None = None,
) -> dict[str, object]:
    environment = os.environ if environ is None else environ
    runtime = getattr(benchmark, "runtime")
    executable = {
        "python": "python",
        "conda": "conda",
        "uv": "uv",
        "docker": "docker",
    }.get(runtime, runtime)
    required_secrets = tuple(getattr(benchmark, "secrets"))
    missing_secrets = [
        name for name in required_secrets if not environment.get(name)
    ]
    resource_acknowledged = (
        getattr(benchmark, "id") in acknowledged_resources
        or "all" in acknowledged_resources
    )
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


def _load_subjects_or_exit(path: Path):
    try:
        return load_subject_registry(path)
    except SubjectRegistryError as exc:
        print(json.dumps({"status": "BLOCKED", "error": str(exc)}, indent=2))
        raise SystemExit(1) from exc


def _handle_subject_commands(args: argparse.Namespace) -> None:
    registry = _load_subjects_or_exit(args.subjects)
    if args.command == "subjects":
        print(
            json.dumps(
                {
                    "registry_version": registry.version,
                    "hash_algorithm": registry.hash_algorithm,
                    "subjects": [
                        {
                            "id": item.id,
                            "benchmark_id": item.benchmark_id,
                            "treatment": item.treatment,
                            "provider": item.provider,
                            "model_env": item.model_env,
                            "api_mode": item.api_mode,
                            "profile_id": item.profile_id,
                            "profile_sha256": item.profile_sha256,
                            "store": item.store,
                        }
                        for item in registry.subjects
                    ],
                    "score_status": "NOT_EXECUTED",
                },
                indent=2,
            )
        )
        return
    if args.command == "subject-doctor":
        categories = ensure_categories(args.category or list(DEFAULT_CATEGORIES))
        try:
            _, case_shard_status = load_case_map(args.case_map, categories)
        except BFCLPackageError as exc:
            print(
                json.dumps(
                    {
                        "status": "BLOCKED",
                        "error": str(exc),
                        "score_status": "NOT_EXECUTED",
                    },
                    indent=2,
                )
            )
            raise SystemExit(1) from exc
        model_key = os.environ.get("AIOS_BENCH_BFCL_MODEL", "").strip() or None
        bfcl_root_value = os.environ.get("BFCL_ROOT", "").strip()
        model_validation = inspect_bfcl_checkout(
            bfcl_root=Path(bfcl_root_value) if bfcl_root_value else None,
            model_key=model_key,
        )
        report = [
            item.admission(
                repository_root=registry.repository_root,
                environ=os.environ,
                resource_acknowledged=args.ack_resource,
                case_shard_resolved=case_shard_status == "RESOLVED",
                model_validation=model_validation,
            )
            for item in registry.subjects
        ]
        ready = all(
            bool(item["execution_admission_ready"]) for item in report
        )
        print(
            json.dumps(
                {
                    "status": "READY_TO_EXECUTE" if ready else "BLOCKED",
                    "categories": list(categories),
                    "case_shard_status": case_shard_status,
                    "model_validation": model_validation,
                    "subjects": report,
                    "score_status": "NOT_EXECUTED",
                },
                indent=2,
            )
        )
        raise SystemExit(0 if ready else 1)
    if args.command == "package-bfcl":
        categories = args.category or list(DEFAULT_CATEGORIES)
        try:
            package = create_bfcl_ab_package(
                registry_path=args.subjects,
                output_dir=args.output_dir,
                categories=categories,
                per_category=args.per_category,
                case_map_path=args.case_map,
                resource_acknowledged=args.ack_resource,
            )
        except BFCLPackageError as exc:
            print(
                json.dumps(
                    {"status": "BLOCKED", "error": str(exc)}, indent=2
                )
            )
            raise SystemExit(1) from exc
        print(
            json.dumps(
                {
                    "status": package.status,
                    "score_status": package.score_status,
                    "output_dir": str(package.output_dir),
                    "manifest": str(package.manifest_path),
                    "commands": str(package.commands_path),
                    "direct_run_manifest": str(package.direct_manifest_path),
                    "aios_run_manifest": str(package.aios_manifest_path),
                    "direct_model_key": package.direct_model_key,
                    "aios_model_key": package.aios_model_key,
                    "profile_sha256": package.profile_sha256,
                    "categories": list(package.categories),
                    "case_shard_status": package.case_shard_status,
                },
                indent=2,
            )
        )
        return
    if args.command == "compare-bfcl":
        try:
            comparison = compare_score_artifacts(
                direct_path=args.direct,
                aios_path=args.aios,
                direct_manifest_path=args.direct_manifest,
                aios_manifest_path=args.aios_manifest,
            )
        except ScoreComparisonError as exc:
            print(
                json.dumps(
                    {"status": "BLOCKED", "error": str(exc)}, indent=2
                )
            )
            raise SystemExit(1) from exc
        rendered = json.dumps(comparison, indent=2) + "\n"
        if args.output:
            args.output.write_text(rendered)
        print(rendered, end="")
        return
    raise RuntimeError(f"unhandled subject command: {args.command}")


def main() -> None:
    parser = argparse.ArgumentParser(prog="aios-bench")
    parser.add_argument(
        "--registry",
        type=Path,
        default=Path("benchmarks/registry.v0.1.json"),
    )
    parser.add_argument(
        "--subjects",
        type=Path,
        default=Path("benchmarks/subjects.v0.1.json"),
    )
    subparsers = parser.add_subparsers(dest="command", required=True)
    subparsers.add_parser("list")
    doctor = subparsers.add_parser("doctor")
    doctor.add_argument("benchmark_id", nargs="?")
    doctor.add_argument(
        "--ack-resource",
        action="append",
        default=[],
        metavar="BENCHMARK_ID",
        help=(
            "Acknowledge the declared resource class for one benchmark; "
            "use 'all' only for an intentional full-registry check."
        ),
    )

    subparsers.add_parser("subjects")
    subject_doctor = subparsers.add_parser("subject-doctor")
    subject_doctor.add_argument("--case-map", type=Path)
    subject_doctor.add_argument("--category", action="append", default=[])
    subject_doctor.add_argument("--ack-resource", action="store_true")

    package = subparsers.add_parser("package-bfcl")
    package.add_argument("--output-dir", type=Path, required=True)
    package.add_argument("--category", action="append", default=[])
    package.add_argument("--per-category", type=int, default=1)
    package.add_argument("--case-map", type=Path)
    package.add_argument("--ack-resource", action="store_true")

    compare = subparsers.add_parser("compare-bfcl")
    compare.add_argument("--direct", type=Path, required=True)
    compare.add_argument("--aios", type=Path, required=True)
    compare.add_argument("--direct-manifest", type=Path, required=True)
    compare.add_argument("--aios-manifest", type=Path, required=True)
    compare.add_argument("--output", type=Path)

    args = parser.parse_args()
    if args.command in {
        "subjects",
        "subject-doctor",
        "package-bfcl",
        "compare-bfcl",
    }:
        _handle_subject_commands(args)
        return

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
                        {
                            "id": item.id,
                            "classification": item.classification,
                            "pin_ready": item.pin_ready,
                        }
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
            print(
                json.dumps(
                    {
                        "status": "BLOCKED",
                        "error": f"unknown benchmark: {args.benchmark_id}",
                    },
                    indent=2,
                )
            )
            raise SystemExit(2) from exc
    acknowledgements = set(args.ack_resource)
    unknown_acknowledgements = (
        acknowledgements
        - {item.id for item in registry.benchmarks}
        - {"all"}
    )
    if unknown_acknowledgements:
        print(
            json.dumps(
                {
                    "status": "BLOCKED",
                    "error": (
                        "unknown resource acknowledgement: "
                        f"{sorted(unknown_acknowledgements)}"
                    ),
                },
                indent=2,
            )
        )
        raise SystemExit(2)
    report = [
        _doctor_item(item, acknowledged_resources=acknowledgements)
        for item in items
    ]
    ready = all(
        bool(item["execution_admission_ready"]) for item in report
    )
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
