from __future__ import annotations

from typing import Any

from .cognition_receipt import CognitionReceiptBuilder


def build_execution_cognition_receipt(
    *,
    request_id: str,
    tool: str,
    scope: str,
    mode: str,
    status: str,
    started_at: str,
    completed_at: str,
    requested_by: dict[str, Any],
    authority_context: dict[str, Any],
    provenance: list[dict[str, Any]],
    handler_invoked: bool,
    error_codes: list[str],
) -> dict[str, Any]:
    """Build the bounded cognition trace for one governed tool execution."""
    builder = CognitionReceiptBuilder(
        trace_id=f"trace-{request_id}",
        request_id=request_id,
        scope_key=scope,
        mode=mode,
        started_at=started_at,
    )
    actor = str(requested_by.get("id") or requested_by.get("type") or "unknown-requester")
    evidence = list(provenance)

    builder.append(
        "intent.received",
        started_at,
        actor,
        {"request_kind": "tool_invocation", "tool": tool},
        evidence,
    )
    builder.append(
        "intent.classified",
        started_at,
        "aios-tools.runner",
        {"intent_class": "bounded_tool_execution", "tool": tool},
    )
    builder.append(
        "scope.candidate_considered",
        started_at,
        "aios-tools.runner",
        {"scope_key": scope, "source": "request_envelope"},
    )
    builder.append(
        "scope.resolved",
        started_at,
        "aios-tools.runner",
        {"scope_key": scope, "resolution": "explicit_request_scope"},
    )
    builder.append(
        "execution.requested",
        started_at,
        actor,
        {"tool": tool, "mode": mode},
    )
    builder.append(
        "execution.eligibility_evaluated",
        completed_at,
        "aios-tools.runner",
        {
            "eligible": handler_invoked,
            "authority_context_keys": sorted(authority_context),
            "error_codes": sorted(error_codes),
        },
    )
    if handler_invoked:
        builder.append(
            "tool.invoked",
            started_at,
            "aios-tools.runner",
            {"tool": tool},
        )

    terminal_type = {
        "COMPLETED": "tool.completed",
        "FAILED": "tool.failed",
        "BLOCKED": "tool.blocked",
        "APPROVAL_REQUIRED": "tool.blocked",
    }[status]
    builder.append(
        terminal_type,
        completed_at,
        "aios-tools.runner",
        {"tool": tool, "status": status, "error_codes": sorted(error_codes)},
    )
    builder.append(
        "receipt.created",
        completed_at,
        "aios-tools.runner",
        {"receipt_kind": "tool_execution", "request_id": request_id},
    )
    return builder.finalize(
        completed_at=completed_at,
        status=status,
        provenance=provenance,
    )
