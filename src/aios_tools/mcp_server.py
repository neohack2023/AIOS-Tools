from __future__ import annotations

import argparse
from typing import Any

from mcp.server.fastmcp import FastMCP

from .runner import invoke

mcp = FastMCP("AIOS-Tools", instructions="Independent AIOS capability and execution layer. All bootstrap tools are read-only and return governed execution receipts.", json_response=True, stateless_http=True)


@mcp.tool()
def system_health(scope: str = "global-working-memory") -> dict[str, Any]:
    """Report AIOS-Tools registry, policy state, and execution-layer identity."""
    return invoke("system.health", {}, scope=scope)


@mcp.tool()
def canonical_hash_json(value: Any, scope: str = "global-working-memory") -> dict[str, Any]:
    """Return a deterministic SHA-256 digest for JSON-compatible data."""
    return invoke("canonical.hash_json", {"value": value}, scope=scope)


@mcp.tool()
def validate_json_schema(schema: dict[str, Any], instance: Any, scope: str = "global-working-memory") -> dict[str, Any]:
    """Validate an instance using JSON Schema Draft 2020-12."""
    return invoke("schema.validate", {"schema": schema, "instance": instance}, scope=scope)


def main() -> None:
    parser = argparse.ArgumentParser(prog="aios-tools-mcp")
    parser.add_argument("--transport", choices=["streamable-http", "stdio"], default="streamable-http")
    args = parser.parse_args()
    mcp.run(transport=args.transport)


if __name__ == "__main__":
    main()
