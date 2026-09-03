#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path

from aios_tools.experimental.execution_trust_binding import (
    MATRIX_PATH,
    admit_and_invoke_read_only,
    build_system_health_binding,
    run_synthetic_matrix,
)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Run disposable AIOS execution trust-binding fixtures."
    )
    parser.add_argument(
        "--matrix",
        type=Path,
        default=MATRIX_PATH,
        help="Path to the frozen ETB matrix JSON.",
    )
    parser.add_argument(
        "--real-read-only",
        action="store_true",
        help="After the matrix passes, gate and invoke the real system.health path.",
    )
    parser.add_argument(
        "--output",
        type=Path,
        help="Optional path for the complete JSON evidence bundle.",
    )
    args = parser.parse_args()

    matrix = run_synthetic_matrix(args.matrix)
    result = {
        "schema": "aios.execution-trust-binding-harness-run.v0.1",
        "matrix": matrix,
        "real_read_only_path": None,
        "authority_transfer": False,
    }

    if args.real_read_only:
        if matrix["passed"]:
            result["real_read_only_path"] = admit_and_invoke_read_only(
                build_system_health_binding(), "system.health", {}
            )
        else:
            result["real_read_only_path"] = {
                "path_status": "BLOCKED_MATRIX_FAILED",
                "executor_invoked": False,
                "authority_transfer": False,
            }

    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(
            json.dumps(result, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
    print(json.dumps(result, indent=2, sort_keys=True))

    real_passed = (
        not args.real_read_only
        or result["real_read_only_path"]["path_status"] == "COMPLETED"
    )
    return 0 if matrix["passed"] and real_passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
