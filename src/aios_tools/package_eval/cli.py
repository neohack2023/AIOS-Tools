from __future__ import annotations

import argparse
import json
import os
from pathlib import Path

from .product_surface import (
    advance_product_surface_receipt,
    initialize_product_surface_receipt,
    validate_product_surface_receipt,
)
from .provider import DEFAULT_RESPONSES_ENDPOINT, execute_openai_pair
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


def _add_build(sub: argparse._SubParsersAction) -> None:
    build = sub.add_parser("build")
    build.add_argument("--package", type=Path, required=True)
    build.add_argument("--fixture", type=Path, required=True)
    build.add_argument("--output-dir", type=Path, required=True)


def _add_grade(sub: argparse._SubParsersAction) -> None:
    grade = sub.add_parser("grade")
    grade.add_argument("--output-text", type=Path, required=True)
    grade.add_argument("--grader", type=Path, required=True)
    grade.add_argument("--result", type=Path)


def _add_compare(sub: argparse._SubParsersAction) -> None:
    compare = sub.add_parser("compare")
    compare.add_argument("--package-off", type=Path, required=True)
    compare.add_argument("--package-on", type=Path, required=True)
    compare.add_argument("--result", type=Path)


def _add_run_openai(sub: argparse._SubParsersAction) -> None:
    run = sub.add_parser("run-openai")
    run.add_argument("--capsule-dir", type=Path, required=True)
    run.add_argument("--package", type=Path, required=True)
    run.add_argument("--model", required=True)
    run.add_argument("--output-dir", type=Path, required=True)
    run.add_argument("--api-key-env", default="OPENAI_API_KEY")
    run.add_argument("--endpoint", default=DEFAULT_RESPONSES_ENDPOINT)
    run.add_argument("--timeout-seconds", type=float, default=300.0)


def _add_product_surface(sub: argparse._SubParsersAction) -> None:
    init = sub.add_parser("product-init")
    init.add_argument("--plan", type=Path, required=True)
    init.add_argument("--manifest", type=Path, required=True)
    init.add_argument("--result", type=Path, required=True)

    advance = sub.add_parser("product-advance")
    advance.add_argument("--receipt", type=Path, required=True)
    advance.add_argument("--state", required=True)
    advance.add_argument("--evidence", type=Path)
    advance.add_argument("--result", type=Path, required=True)

    validate = sub.add_parser("product-validate")
    validate.add_argument("--receipt", type=Path, required=True)


def main() -> None:
    parser = argparse.ArgumentParser(prog="aios-package-eval")
    sub = parser.add_subparsers(dest="command", required=True)
    _add_build(sub)
    _add_grade(sub)
    _add_compare(sub)
    _add_run_openai(sub)
    _add_product_surface(sub)
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

        if args.command == "run-openai":
            api_key = os.environ.get(args.api_key_env, "")
            if not api_key:
                raise PortablePackageEvalError(
                    f"required credential environment variable is missing: "
                    f"{args.api_key_env}"
                )
            receipt = execute_openai_pair(
                capsule_dir=args.capsule_dir,
                package_path=args.package,
                model=args.model,
                api_key=api_key,
                output_dir=args.output_dir,
                endpoint=args.endpoint,
                timeout_seconds=args.timeout_seconds,
            )
            _emit(receipt)
            return

        if args.command == "product-init":
            manifest = _load_json(args.manifest)
            plan = _load_json(args.plan)
            package = manifest.get("package")
            if not isinstance(package, dict):
                raise PortablePackageEvalError("manifest.package must be an object")
            receipt = initialize_product_surface_receipt(
                plan=plan,
                package_sha256=str(package.get("sha256", "")),
                fixture_sha256=str(manifest.get("fixture_sha256", "")),
            )
            _emit(receipt, args.result)
            return

        if args.command == "product-advance":
            evidence = _load_json(args.evidence) if args.evidence else None
            receipt = advance_product_surface_receipt(
                receipt=_load_json(args.receipt),
                next_state=args.state,
                evidence=evidence,
            )
            _emit(receipt, args.result)
            return

        if args.command == "product-validate":
            _emit(validate_product_surface_receipt(_load_json(args.receipt)))
            return
    except PortablePackageEvalError as exc:
        _emit({"status": "BLOCKED", "error": str(exc)})
        raise SystemExit(2) from exc


if __name__ == "__main__":
    main()
