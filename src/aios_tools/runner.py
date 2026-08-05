from __future__ import annotations

from typing import Any
from uuid import uuid4

from .config import ConfigurationError, load_policy, load_registry, validate_request
from .envelope import ExecutionReceipt, ToolError, utc_now
from .runtime_cognition import build_execution_cognition_receipt
from .tools import HANDLERS


def _receipt(
    *,
    request_id: str,
    tool: str,
    tool_version: str,
    scope: str,
    mode: str,
    status: str,
    started_at: str,
    registry_version: str = "UNKNOWN",
    policy_version: str = "UNKNOWN",
    requested_by: dict[str, Any] | None = None,
    authority_context: dict[str, Any] | None = None,
    output: dict[str, Any] | None = None,
    errors: list[ToolError] | None = None,
    provenance: list[dict[str, Any]] | None = None,
    handler_invoked: bool = False,
) -> dict[str, Any]:
    completed_at = utc_now()
    requested_by = requested_by or {}
    authority_context = authority_context or {}
    provenance = provenance or []
    errors = errors or []
    cognition_receipt = build_execution_cognition_receipt(
        request_id=request_id,
        tool=tool,
        scope=scope,
        mode=mode,
        status=status,
        started_at=started_at,
        completed_at=completed_at,
        requested_by=requested_by,
        authority_context=authority_context,
        provenance=provenance,
        handler_invoked=handler_invoked,
        error_codes=[error.code for error in errors],
    )
    return ExecutionReceipt(
        request_id=request_id,
        tool=tool,
        tool_version=tool_version,
        scope=scope,
        mode=mode,
        status=status,
        started_at=started_at,
        completed_at=completed_at,
        registry_version=registry_version,
        policy_version=policy_version,
        requested_by=requested_by,
        authority_context=authority_context,
        output=output or {},
        errors=errors,
        provenance=provenance,
        cognition_receipt=cognition_receipt,
    ).to_dict()


def _write_approval_error(authority_context: dict[str, Any], *, tool: str, scope: str) -> ToolError | None:
    approval = authority_context.get("approval")
    if not isinstance(approval, dict):
        return ToolError(code="APPROVAL_REQUIRED", message="WRITE mode requires authority_context.approval")
    if approval.get("approved") is not True:
        return ToolError(code="APPROVAL_REQUIRED", message="WRITE approval must set approved=true")
    approved_by = approval.get("approved_by")
    if not isinstance(approved_by, str) or not approved_by.strip():
        return ToolError(code="APPROVAL_INVALID", message="WRITE approval requires approved_by")
    approved_tool = approval.get("tool")
    if approved_tool not in (None, tool):
        return ToolError(code="APPROVAL_SCOPE_MISMATCH", message="approval does not cover the requested tool")
    approved_scope = approval.get("scope")
    if approved_scope not in (None, scope):
        return ToolError(code="APPROVAL_SCOPE_MISMATCH", message="approval does not cover the requested scope")
    return None


def invoke(
    tool: str,
    payload: dict[str, Any],
    *,
    request_id: str | None = None,
    scope: str = "global-working-memory",
    mode: str = "READ_ONLY",
    requested_by: dict[str, Any] | None = None,
    authority_context: dict[str, Any] | None = None,
    provenance: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    request_id = request_id or f"request-{uuid4()}"
    requested_by = requested_by or {"type": "SERVICE", "id": "aios-tools-python"}
    authority_context = authority_context or {}
    provenance = provenance or []
    started_at = utc_now()

    try:
        policy = load_policy()
        registry, registry_version = load_registry(HANDLERS)
    except ConfigurationError as exc:
        return _receipt(
            request_id=request_id,
            tool=tool,
            tool_version="UNKNOWN",
            scope=scope,
            mode=mode,
            status="BLOCKED",
            started_at=started_at,
            requested_by=requested_by,
            authority_context=authority_context,
            provenance=provenance,
            errors=[ToolError(code="CONFIGURATION_INVALID", message=str(exc))],
        )

    policy_version = policy["policy_version"]
    metadata = registry.get(tool)
    tool_version = metadata["version"] if metadata else "UNKNOWN"
    request = {
        "request_id": request_id,
        "tool": tool,
        "tool_version": tool_version,
        "scope": scope,
        "mode": mode,
        "requested_by": requested_by,
        "input": payload,
        "authority_context": authority_context,
        "provenance": provenance,
    }
    request_errors = validate_request(request)
    if request_errors:
        return _receipt(
            request_id=request_id,
            tool=tool,
            tool_version=tool_version,
            scope=scope,
            mode=mode,
            status="BLOCKED",
            started_at=started_at,
            registry_version=registry_version,
            policy_version=policy_version,
            requested_by=requested_by,
            authority_context=authority_context,
            provenance=provenance,
            errors=[ToolError(code="REQUEST_INVALID", message="request contract validation failed", details={"errors": request_errors})],
        )

    if metadata is None:
        return _receipt(
            request_id=request_id,
            tool=tool,
            tool_version="UNKNOWN",
            scope=scope,
            mode=mode,
            status="BLOCKED",
            started_at=started_at,
            registry_version=registry_version,
            policy_version=policy_version,
            requested_by=requested_by,
            authority_context=authority_context,
            provenance=provenance,
            errors=[ToolError(code="TOOL_NOT_REGISTERED", message=f"Unknown tool: {tool}")],
        )

    if mode not in policy["allowed_modes"]:
        return _receipt(
            request_id=request_id,
            tool=tool,
            tool_version=tool_version,
            scope=scope,
            mode=mode,
            status="BLOCKED",
            started_at=started_at,
            registry_version=registry_version,
            policy_version=policy_version,
            requested_by=requested_by,
            authority_context=authority_context,
            provenance=provenance,
            errors=[ToolError(code="MODE_GLOBALLY_BLOCKED", message=f"policy does not allow mode: {mode}")],
        )
    if mode != metadata["mode"]:
        return _receipt(
            request_id=request_id,
            tool=tool,
            tool_version=tool_version,
            scope=scope,
            mode=mode,
            status="BLOCKED",
            started_at=started_at,
            registry_version=registry_version,
            policy_version=policy_version,
            requested_by=requested_by,
            authority_context=authority_context,
            provenance=provenance,
            errors=[ToolError(code="MODE_NOT_ALLOWED", message=f"{tool} permits {metadata['mode']}, requested {mode}")],
        )
    if metadata["authority_transfer"] is not False or policy["authority_transfer_allowed"] is not False:
        return _receipt(
            request_id=request_id,
            tool=tool,
            tool_version=tool_version,
            scope=scope,
            mode=mode,
            status="BLOCKED",
            started_at=started_at,
            registry_version=registry_version,
            policy_version=policy_version,
            requested_by=requested_by,
            authority_context=authority_context,
            provenance=provenance,
            errors=[ToolError(code="AUTHORITY_TRANSFER_BLOCKED", message="authority transfer is forbidden")],
        )

    if mode == "WRITE":
        approval_error = _write_approval_error(authority_context, tool=tool, scope=scope)
        if approval_error is not None:
            return _receipt(
                request_id=request_id,
                tool=tool,
                tool_version=tool_version,
                scope=scope,
                mode=mode,
                status="APPROVAL_REQUIRED",
                started_at=started_at,
                registry_version=registry_version,
                policy_version=policy_version,
                requested_by=requested_by,
                authority_context=authority_context,
                provenance=provenance,
                errors=[approval_error],
            )

    handler = HANDLERS.get(tool)
    if handler is None:
        return _receipt(
            request_id=request_id,
            tool=tool,
            tool_version=tool_version,
            scope=scope,
            mode=mode,
            status="BLOCKED",
            started_at=started_at,
            registry_version=registry_version,
            policy_version=policy_version,
            requested_by=requested_by,
            authority_context=authority_context,
            provenance=provenance,
            errors=[ToolError(code="HANDLER_NOT_REGISTERED", message=f"No handler is bound for {tool}")],
        )

    try:
        output = handler(payload)
        if tool == "system.health":
            output = {
                **output,
                "registry_version": registry_version,
                "policy_version": policy_version,
                "tools": registry,
                "policy": {
                    "default_mode": policy["default_mode"],
                    "allowed_modes": policy["allowed_modes"],
                    "durable_writes_enabled": policy["durable_writes_enabled"],
                    "external_network_effects_enabled": policy["external_network_effects_enabled"],
                    "authority_transfer_allowed": policy["authority_transfer_allowed"],
                    "approval_required_for": policy["approval_required_for"],
                    "write_scope": policy.get("write_scope"),
                },
            }
        status = "COMPLETED"
        errors: list[ToolError] = []
    except (TypeError, ValueError) as exc:
        output = {}
        status = "FAILED"
        errors = [ToolError(code="INVALID_INPUT", message=str(exc))]
    except Exception:
        output = {}
        status = "FAILED"
        errors = [ToolError(code="INTERNAL_ERROR", message="tool execution failed unexpectedly")]

    return _receipt(
        request_id=request_id,
        tool=tool,
        tool_version=tool_version,
        scope=scope,
        mode=mode,
        status=status,
        started_at=started_at,
        registry_version=registry_version,
        policy_version=policy_version,
        requested_by=requested_by,
        authority_context=authority_context,
        output=output,
        errors=errors,
        provenance=provenance,
        handler_invoked=True,
    )
