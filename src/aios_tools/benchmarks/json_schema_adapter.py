from __future__ import annotations

import argparse
import json
from pathlib import Path

from jsonschema import Draft202012Validator


def run_case(*, suite_root: Path, relative_file: Path, case_index: int) -> dict[str, object]:
    case_path = suite_root / relative_file
    groups = json.loads(case_path.read_text(encoding="utf-8"))
    if not isinstance(groups, list) or not groups:
        raise ValueError(f"JSON Schema suite file has no test groups: {relative_file}")
    try:
        group = groups[case_index]
    except IndexError as exc:
        raise ValueError(f"case index {case_index} is outside {relative_file}") from exc
    if not isinstance(group, dict):
        raise ValueError(f"case index {case_index} in {relative_file} is not an object")
    validator = Draft202012Validator(group["schema"])
    results: list[dict[str, object]] = []
    for test in group["tests"]:
        actual = validator.is_valid(test["data"])
        expected = bool(test["valid"])
        results.append(
            {
                "description": test["description"],
                "expected": expected,
                "actual": actual,
                "passed": actual == expected,
            }
        )
    passed = all(bool(result["passed"]) for result in results)
    return {
        "classification": "STANDARDS_CONFORMANCE",
        "suite_file": str(relative_file),
        "case_index": case_index,
        "case_description": group.get("description"),
        "passed": passed,
        "tests": results,
    }


def main() -> None:
    parser = argparse.ArgumentParser(prog="python -m aios_tools.benchmarks.json_schema_adapter")
    parser.add_argument("--suite-root", type=Path, required=True)
    parser.add_argument("--file", type=Path, required=True)
    parser.add_argument("--case-index", type=int, default=0)
    args = parser.parse_args()
    try:
        result = run_case(
            suite_root=args.suite_root,
            relative_file=args.file,
            case_index=args.case_index,
        )
    except (OSError, KeyError, TypeError, ValueError, json.JSONDecodeError) as exc:
        print(json.dumps({"status": "BLOCKED", "error": str(exc)}, indent=2))
        raise SystemExit(2) from exc
    print(json.dumps(result, indent=2))
    raise SystemExit(0 if result["passed"] else 1)


if __name__ == "__main__":
    main()
