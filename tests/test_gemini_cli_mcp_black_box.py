from __future__ import annotations

import asyncio
import os
import sys
from typing import Any

import pytest
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client


EXPECTED_MCP_TOOLS = {
    "system_health",
    "canonical_hash_json",
    "validate_json_schema",
}


def _structured(result: Any) -> dict[str, Any]:
    structured = getattr(result, "structuredContent", None)
    if structured is None:
        structured = getattr(result, "structured_content", None)
    assert isinstance(structured, dict)
    return structured


def _assert_governed_receipt(receipt: dict[str, Any], tool: str) -> None:
    assert receipt["tool"] == tool
    assert receipt["status"] == "COMPLETED"
    assert receipt["authority_transfer"] is False
    assert receipt["external_effects"] == []
    assert receipt["requested_by"] == {"type": "LLM", "id": "aios-tools-mcp"}
    assert isinstance(receipt["authority_context"], dict)
    assert isinstance(receipt["cognition_receipt"], dict)


async def _exercise_stdio_boundary() -> None:
    server = StdioServerParameters(
        command=sys.executable,
        args=["-m", "aios_tools.mcp_server", "--transport", "stdio"],
        env=dict(os.environ),
    )

    async with stdio_client(server) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()

            listed = await session.list_tools()
            assert {tool.name for tool in listed.tools} == EXPECTED_MCP_TOOLS

            health = _structured(await session.call_tool("system_health", arguments={}))
            _assert_governed_receipt(health, "system.health")

            digest = _structured(
                await session.call_tool(
                    "canonical_hash_json",
                    arguments={"value": {"b": 2, "a": 1}},
                )
            )
            _assert_governed_receipt(digest, "canonical.hash_json")
            assert isinstance(digest["output"].get("digest"), str)

            validation = _structured(
                await session.call_tool(
                    "validate_json_schema",
                    arguments={
                        "schema": {
                            "$schema": "https://json-schema.org/draft/2020-12/schema",
                            "type": "object",
                            "required": ["name"],
                            "properties": {"name": {"type": "string"}},
                            "additionalProperties": False,
                        },
                        "instance": {"name": "Gemini"},
                    },
                )
            )
            _assert_governed_receipt(validation, "schema.validate")
            assert validation["output"]["valid"] is True

            malformed = await session.call_tool("canonical_hash_json", arguments={})
            assert malformed.isError is True

            with pytest.raises(Exception):
                await session.call_tool("tool_that_does_not_exist", arguments={})


def test_mcp_stdio_black_box_contract() -> None:
    asyncio.run(_exercise_stdio_boundary())
