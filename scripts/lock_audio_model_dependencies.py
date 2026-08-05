#!/usr/bin/env python3
"""Governed Slice 2A dependency lock command surface.

Only ``fetch`` may access the network. Benchmarking and runtime review are offline.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from audio_model_lock_common import *  # noqa: F401,F403,E402
from audio_model_lock_fetch import run_fetch  # noqa: E402
from audio_model_lock_benchmark import run_benchmark  # noqa: E402

def _contains_tool_identity(path: Path) -> bool:
    if not path.is_file():
        return False
    try:
        return TOOL_IDENTITY in path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        return False


def run_review_runtime(args: argparse.Namespace) -> int:
    root = args.repo_root.resolve()
    surfaces = {
        "registry": root / "registry/tools.v0.1.json",
        "policy": root / "policies/execution-policy.v0.1.json",
        "shared_handler": root / "src/aios_tools/tools.py",
        "runner": root / "src/aios_tools/runner.py",
    }
    checks: dict[str, Any] = {name: _contains_tool_identity(path) for name, path in surfaces.items()}
    contract_matches = sorted(
        str(path.relative_to(root))
        for path in (root / "contracts").glob("*.json")
        if _contains_tool_identity(path)
    ) if (root / "contracts").is_dir() else []
    checks["contracts"] = contract_matches
    implementation_present = bool(checks["registry"] and checks["policy"] and checks["shared_handler"] and contract_matches)
    status = "RUNTIME_IMPLEMENTATION_REVIEW_REQUIRED" if not implementation_present else "RUNTIME_IMPLEMENTATION_PRESENT_REQUIRES_BEHAVIORAL_REVIEW"
    receipt = {
        "schema_version": "0.1.0",
        "status": status,
        "run_classification": "STATIC_RUNTIME_ADMISSION_SURFACE_REVIEW",
        "profile_id": PROFILE_ID,
        "tool_identity": TOOL_IDENTITY,
        "reviewed_at": utc_now(),
        "authority_transfer": False,
        "checks": checks,
        "implementation_present": implementation_present,
        "decision": "SEPARATE_BOUNDED_RUNTIME_IMPLEMENTATION_PR_REQUIRED" if not implementation_present else "DO_NOT_ADMIT_UNTIL_FULL_RUNTIME_TESTS_PASS",
        "runtime_admission": False,
        "pilot_authorized": False,
    }
    write_json(args.output, receipt)
    print("RUNTIME_REVIEW_RECEIPT_JSON=" + json.dumps(receipt, sort_keys=True, separators=(",", ":")))
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser()
    subparsers = parser.add_subparsers(dest="command", required=True)

    fetch_parser = subparsers.add_parser("fetch")
    fetch_parser.add_argument("--manifest", required=True, type=Path)
    fetch_parser.add_argument("--quarantine", required=True, type=Path)
    fetch_parser.add_argument("--output", required=True, type=Path)
    fetch_parser.add_argument("--allow-existing", action="store_true")
    fetch_parser.set_defaults(func=run_fetch)

    benchmark_parser = subparsers.add_parser("benchmark")
    benchmark_parser.add_argument("--manifest", required=True, type=Path)
    benchmark_parser.add_argument("--fetch-receipt", required=True, type=Path)
    benchmark_parser.add_argument("--quarantine", required=True, type=Path)
    benchmark_parser.add_argument("--bench-dir", required=True, type=Path)
    benchmark_parser.add_argument("--output", required=True, type=Path)
    benchmark_parser.add_argument("--profile-output", required=True, type=Path)
    benchmark_parser.add_argument("--fixture-seconds", type=float, default=5.0)
    benchmark_parser.add_argument("--thread-count", type=int, default=1)
    benchmark_parser.set_defaults(func=run_benchmark)

    review_parser = subparsers.add_parser("review-runtime")
    review_parser.add_argument("--repo-root", required=True, type=Path)
    review_parser.add_argument("--output", required=True, type=Path)
    review_parser.set_defaults(func=run_review_runtime)
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        return int(args.func(args))
    except DependencyLockError as exc:
        print(json.dumps({"status": "FAILED", "error": str(exc)}, sort_keys=True))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
