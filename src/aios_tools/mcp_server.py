from __future__ import annotations

import argparse
from typing import Any

from mcp.server.fastmcp import FastMCP

from .runner import invoke

mcp = FastMCP(
    "AIOS-Tools",
    instructions="Independent AIOS capability and execution layer. All tools return governed execution receipts.",
    json_response=True,
    stateless_http=True,
)

MCP_REQUESTER = {"type": "LLM", "id": "aios-tools-mcp"}


@mcp.tool()
def system_health(scope: str = "global-working-memory") -> dict[str, Any]:
    """Report AIOS-Tools registry, policy state, and execution-layer identity."""
    return invoke("system.health", {}, scope=scope, requested_by=MCP_REQUESTER)


@mcp.tool()
def canonical_hash_json(value: Any, scope: str = "global-working-memory") -> dict[str, Any]:
    """Return a deterministic SHA-256 digest for JSON-compatible data."""
    return invoke("canonical.hash_json", {"value": value}, scope=scope, requested_by=MCP_REQUESTER)


@mcp.tool()
def validate_json_schema(schema: dict[str, Any], instance: Any, scope: str = "global-working-memory") -> dict[str, Any]:
    """Validate an instance using JSON Schema Draft 2020-12."""
    return invoke("schema.validate", {"schema": schema, "instance": instance}, scope=scope, requested_by=MCP_REQUESTER)


@mcp.tool()
def browser_inspect(
    url: str,
    visible_text_chars: int = 50000,
    elapsed_seconds: int = 60,
    scope: str = "global-working-memory",
) -> dict[str, Any]:
    """Inspect one explicit public HTTP(S) origin through the governed 02B browser runtime."""
    return invoke(
        "browser.inspect",
        {"url": url, "visible_text_chars": visible_text_chars, "elapsed_seconds": elapsed_seconds},
        scope=scope,
        requested_by=MCP_REQUESTER,
    )


@mcp.tool()
def browser_profile_replay(
    profile_id: str,
    scope: str = "global-working-memory",
) -> dict[str, Any]:
    """Replay one registered read-only browser site profile in a fresh session."""
    return invoke(
        "browser.profile.replay",
        {"profile_id": profile_id},
        scope=scope,
        requested_by=MCP_REQUESTER,
    )


@mcp.tool()
def browser_runtime_status(scope: str = "global-working-memory") -> dict[str, Any]:
    """Read the governed browser runtime activation and protected-store state."""
    return invoke(
        "browser.runtime.status",
        {},
        scope=scope,
        requested_by=MCP_REQUESTER,
    )


@mcp.tool()
def browser_mutate_request(
    payload: dict[str, Any],
    authority_context: dict[str, Any],
    scope: str = "global-working-memory",
) -> dict[str, Any]:
    """Execute one exact approved remote HTTP mutation with fresh readback."""
    return invoke(
        "browser.mutate.request",
        payload,
        scope=scope,
        mode="WRITE",
        requested_by=MCP_REQUESTER,
        authority_context=authority_context,
    )


@mcp.tool()
def browser_mutate_reversible(
    payload: dict[str, Any],
    authority_context: dict[str, Any],
    scope: str = "global-working-memory",
) -> dict[str, Any]:
    """Execute one exact approved reversible mutation and verify rollback."""
    return invoke(
        "browser.mutate.reversible",
        payload,
        scope=scope,
        mode="WRITE",
        requested_by=MCP_REQUESTER,
        authority_context=authority_context,
    )


@mcp.tool()
def browser_upload_execute(
    payload: dict[str, Any],
    authority_context: dict[str, Any],
    scope: str = "global-working-memory",
) -> dict[str, Any]:
    """Populate one governed file input under an exact remote mutation permit."""
    return invoke(
        "browser.upload.execute",
        payload,
        scope=scope,
        mode="WRITE",
        requested_by=MCP_REQUESTER,
        authority_context=authority_context,
    )


@mcp.tool()
def browser_session_capture(
    payload: dict[str, Any],
    authority_context: dict[str, Any],
    scope: str = "global-working-memory",
) -> dict[str, Any]:
    """Open a headed human-controlled authentication takeover and seal verified state."""
    return invoke(
        "browser.session.capture",
        payload,
        scope=scope,
        mode="WRITE",
        requested_by=MCP_REQUESTER,
        authority_context=authority_context,
    )


@mcp.tool()
def browser_download_promote(
    payload: dict[str, Any],
    authority_context: dict[str, Any],
    scope: str = "global-working-memory",
) -> dict[str, Any]:
    """Promote one verified quarantined download under registered profile rules."""
    return invoke(
        "browser.download.promote",
        payload,
        scope=scope,
        mode="WRITE",
        requested_by=MCP_REQUESTER,
        authority_context=authority_context,
    )


def main() -> None:
    parser = argparse.ArgumentParser(prog="aios-tools-mcp")
    parser.add_argument("--transport", choices=["streamable-http", "stdio"], default="streamable-http")
    args = parser.parse_args()
    mcp.run(transport=args.transport)


if __name__ == "__main__":
    main()
