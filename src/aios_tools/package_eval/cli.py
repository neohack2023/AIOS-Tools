from __future__ import annotations

import argparse
import json
from pathlib import Path

from .runtime import (
    PortablePackageEvalError,
    build_eval_capsule,
    compare_grade_results,
    grade_output_text,
)


def _load_json(path: Path) -> dict[str, object]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise PortablePackageEvalError(f"cannot load JSON: {path}: {exc}") from exc
    if not isinstance(value, dict):
        raise PortablePackageEvalError(f"JSON root must be an object: {path}")
    return value


def _emit(payload: object, output: Path | None = None) -> None:
    text = json.dumps(payload, indent=2, sort_keys=True) + "\n"
    if output is not None:
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(text, encoding="utf-8")
    print(text, end="")


def main() -> None:
    parser = argparse.ArgumentParser(prog="aios-package-eval")
    sub = parser.add_subparsers(dest="command", required=True)

    build = sub.add_parser("build")
    build.add_argument("--package", type=Path, required=True)
    build.add_argument("--fixture", type=Path, required=True)
    build.add_argument("--output-dir", type=Path, required=True)

    grade = sub.add_parser("grade")
    grade.add_argument("--output-text", type=Path, required=True)
    grade.add_argument("--grader", type=Path, required=True)
    grade.add_argument("--result", type=Path)

    compare = sub.add_parser("compare")
    compare.add_argument("--package-off", type=Path, required=True)
    compare.add_argument("--package-on", type=Path, required=True)
    compare.add_argument("--result", type=Path)

    args = parser.parse_args()
    try:
        if args.command == "build":
            capsule = build_eval_capsule(
                package_path=args.package,
                fixture_path=args.fixture,
                output_dir=args.output_dir,
            )
            _emit({
                "status": capsule.status,
                "output_dir": str(capsule.output_dir),
                "manifest": str(capsule.manifest_path),
                "package_sha256": capsule.package_sha256,
                "fixture_sha256": capsule.fixture_sha256,
                "score_status": "NOT_EXECUTED",
            })
            return
        if args.command == "grade":
            result = grade_output_text(
                output_text=args.output_text.read_text(encoding="utf-8"),
                grader_contract=_load_json(args.grader),
            )
            _emit(result, args.result)
            raise SystemExit(0 if result["deterministic_status"] == "PASS" else 1)
        if args.command == "compare":
            result = compare_grade_results(
                package_off=_load_json(args.package_off),
                package_on=_load_json(args.package_on),
            )
            _emit(result, args.result)
            return
    except PortablePackageEvalError as exc:
        _emit({"status": "BLOCKED", "error": str(exc)})
        raise SystemExit(2) from exc


if __name__ == "__main__":
    main()
