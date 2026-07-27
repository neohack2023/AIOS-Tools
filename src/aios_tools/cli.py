from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

from .runner import invoke
from .tools import TOOL_REGISTRY


def parse_json_input(raw: str) -> dict[str, Any]:
    if raw.startswith("@"):
        raw = Path(raw[1:]).read_text(encoding="utf-8")
    value = json.loads(raw)
    if not isinstance(value, dict):
        raise ValueError("tool input must be a JSON object")
    return value


def main() -> None:
    parser = argparse.ArgumentParser(prog="aios-tools")
    subparsers = parser.add_subparsers(dest="command", required=True)
    subparsers.add_parser("list", help="List registered tools")
    invoke_parser = subparsers.add_parser("invoke", help="Invoke a registered tool")
    invoke_parser.add_argument("tool")
    invoke_parser.add_argument("--input", required=True)
    invoke_parser.add_argument("--scope", default="global-working-memory")
    invoke_parser.add_argument("--mode", default="READ_ONLY")
    invoke_parser.add_argument("--request-id")
    args = parser.parse_args()
    if args.command == "list":
        print(json.dumps(TOOL_REGISTRY, indent=2, sort_keys=True))
        return
    try:
        payload = parse_json_input(args.input)
    except (OSError, json.JSONDecodeError, ValueError) as exc:
        print(json.dumps({"status": "FAILED", "error": str(exc)}), file=sys.stderr)
        raise SystemExit(2) from exc
    result = invoke(args.tool, payload, request_id=args.request_id, scope=args.scope, mode=args.mode)
    print(json.dumps(result, indent=2, sort_keys=True))
    raise SystemExit(0 if result["status"] == "COMPLETED" else 1)


if __name__ == "__main__":
    main()
