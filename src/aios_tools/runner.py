from __future__ import annotations

from typing import Any
from uuid import uuid4

from .envelope import ExecutionReceipt, ToolError, utc_now
from .tools import HANDLERS, TOOL_REGISTRY


def invoke(tool: str, payload: dict[str, Any], *, request_id: str | None = None, scope: str = "global-working-memory", mode: str = "READ_ONLY", provenance: list[dict[str, Any]] | None = None) -> dict[str, Any]:
    request_id = request_id or f"request-{uuid4()}"
    started_at = utc_now()
    metadata = TOOL_REGISTRY.get(tool)
    if metadata is None:
        return ExecutionReceipt(request_id=request_id, tool=tool, tool_version="UNKNOWN", scope=scope, mode=mode, status="BLOCKED", started_at=started_at, completed_at=utc_now(), errors=[ToolError(code="TOOL_NOT_REGISTERED", message=f"Unknown tool: {tool}")], provenance=provenance or []).to_dict()
    if mode != metadata["mode"]:
        return ExecutionReceipt(request_id=request_id, tool=tool, tool_version=metadata["version"], scope=scope, mode=mode, status="BLOCKED", started_at=started_at, completed_at=utc_now(), errors=[ToolError(code="MODE_NOT_ALLOWED", message=f"{tool} permits {metadata['mode']}, requested {mode}")], provenance=provenance or []).to_dict()
    try:
        output = HANDLERS[tool](payload)
        status = "COMPLETED"
        errors: list[ToolError] = []
    except (TypeError, ValueError) as exc:
        output = {}
        status = "FAILED"
        errors = [ToolError(code="INVALID_INPUT", message=str(exc))]
    return ExecutionReceipt(request_id=request_id, tool=tool, tool_version=metadata["version"], scope=scope, mode=mode, status=status, started_at=started_at, completed_at=utc_now(), output=output, errors=errors, provenance=provenance or []).to_dict()
