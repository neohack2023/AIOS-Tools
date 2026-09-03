from __future__ import annotations

from typing import Any
from uuid import uuid4

from .browser.policy import BrowserConfigurationError, browser_network_tool_admitted
from .browser.mutation import MutationPolicyError, build_mutation_grant
from .browser.session_capture import SessionCapturePolicyError, build_session_capture_grant
from .config import ConfigurationError, load_policy, load_registry, validate_request
from .envelope import ExecutionReceipt, ToolError, utc_now
from .execution_trust import (
    build_runtime_system_health_binding,
    evaluate_trust_binding,
)
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
    effect_class: str = "UNKNOWN",
    registry_version: str = "UNKNOWN",
    policy_version: str = "UNKNOWN",
    requested_by: dict[str, Any] | None = None,
    authority_context: dict[str, Any] | None = None,
    output: dict[str, Any] | None = None,
    errors: list[ToolError] | None = None,
    provenance: list[dict[str, Any]] | None = None,
    handler_invoked: bool = False,
    external_effects: list[dict[str, Any]] | None = None,
    trust_binding_receipt: dict[str, Any] | None = None,
) -> dict[str, Any]:
    completed_at = utc_now()
    requested_by = requested_by or {}
    authority_context = authority_context or {}
    provenance = provenance or []
    errors = errors or []
    external_effects = external_effects or []
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
        effect_class=effect_class,
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
        trust_binding_receipt=trust_binding_receipt or {},
        external_effects=external_effects,
    ).to_dict()


def _browser_external_effects(tool: str, effect_class: str, output: dict[str, Any]) -> list[dict[str, Any]]:
    if not tool.startswith("browser."):
        return []
    if effect_class in {"REMOTE_MUTATION_REVERSIBLE", "REMOTE_MUTATION_HIGH_IMPACT"}:
        target_origin = output.get("target_origin")
        terminal_status = output.get("terminal_status")
        method = output.get("method")
        if not isinstance(target_origin, str) or not isinstance(terminal_status, str):
            return []
        mutation_count = output.get("mutation_count", 1 if output.get("response_status") is not None else 0)
        if not isinstance(mutation_count, int):
            mutation_count = 0
        result = {
            "effect_class": effect_class,
            "capability_id": "cap:browser-control",
            "target_origin": target_origin,
            "mutation_count": mutation_count,
            "method": method if isinstance(method, str) else "UNKNOWN",
            "terminal_status": terminal_status,
        }
        if effect_class == "REMOTE_MUTATION_REVERSIBLE":
            result["rollback_attempted"] = bool(output.get("rollback_attempted"))
            result["rollback_verified"] = bool(output.get("rollback_verified"))
        return [result]
    if effect_class != "READ_NETWORK":
        return []
    evidence = output.get("evidence")
    if not isinstance(evidence, dict):
        return []
    network = evidence.get("network")
    if not isinstance(network, list):
        network = []
    request_count = sum(
        1 for item in network
        if isinstance(item, dict) and item.get("event") == "request"
    )
    budget_used = output.get("budget_used")
    if not isinstance(budget_used, dict):
        budget_used = {}
    websocket_count = int(budget_used.get("websockets", 0))
    if request_count == 0 and websocket_count == 0:
        return []
    target_origin = output.get("target_origin")
    terminal_status = output.get("terminal_status")
    if not isinstance(target_origin, str) or not isinstance(terminal_status, str):
        return []
    return [{
        "effect_class": "READ_NETWORK",
        "capability_id": "cap:browser-control",
        "target_origin": target_origin,
        "request_count": request_count,
        "websocket_count": websocket_count,
        "terminal_status": terminal_status,
    }]

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
            request_id=request_id, tool=tool, tool_version="UNKNOWN", scope=scope, mode=mode,
            status="BLOCKED", started_at=started_at, requested_by=requested_by,
            authority_context=authority_context, provenance=provenance,
            errors=[ToolError(code="CONFIGURATION_INVALID", message=str(exc))],
        )

    policy_version = policy["policy_version"]
    metadata = registry.get(tool)
    tool_version = metadata["version"] if metadata else "UNKNOWN"
    effect_class = metadata["effect_class"] if metadata else "UNKNOWN"
    request = {
        "request_id": request_id, "tool": tool, "tool_version": tool_version, "scope": scope,
        "mode": mode, "requested_by": requested_by, "input": payload,
        "authority_context": authority_context, "provenance": provenance,
    }
    request_errors = validate_request(request)
    if request_errors:
        return _receipt(
            request_id=request_id, tool=tool, tool_version=tool_version, scope=scope, mode=mode,
            effect_class=effect_class, status="BLOCKED", started_at=started_at,
            registry_version=registry_version, policy_version=policy_version,
            requested_by=requested_by, authority_context=authority_context, provenance=provenance,
            errors=[ToolError(code="REQUEST_INVALID", message="request contract validation failed", details={"errors": request_errors})],
        )

    if metadata is None:
        return _receipt(
            request_id=request_id, tool=tool, tool_version="UNKNOWN", scope=scope, mode=mode,
            effect_class="UNKNOWN", status="BLOCKED", started_at=started_at,
            registry_version=registry_version, policy_version=policy_version,
            requested_by=requested_by, authority_context=authority_context, provenance=provenance,
            errors=[ToolError(code="TOOL_NOT_REGISTERED", message=f"Unknown tool: {tool}")],
        )

    if mode not in policy["allowed_modes"]:
        return _receipt(
            request_id=request_id, tool=tool, tool_version=tool_version, scope=scope, mode=mode,
            effect_class=effect_class, status="BLOCKED", started_at=started_at,
            registry_version=registry_version, policy_version=policy_version,
            requested_by=requested_by, authority_context=authority_context, provenance=provenance,
            errors=[ToolError(code="MODE_GLOBALLY_BLOCKED", message=f"policy does not allow mode: {mode}")],
        )
    if mode != metadata["mode"]:
        return _receipt(
            request_id=request_id, tool=tool, tool_version=tool_version, scope=scope, mode=mode,
            effect_class=effect_class, status="BLOCKED", started_at=started_at,
            registry_version=registry_version, policy_version=policy_version,
            requested_by=requested_by, authority_context=authority_context, provenance=provenance,
            errors=[ToolError(code="MODE_NOT_ALLOWED", message=f"{tool} permits {metadata['mode']}, requested {mode}")],
        )
    if metadata["authority_transfer"] is not False or policy["authority_transfer_allowed"] is not False:
        return _receipt(
            request_id=request_id, tool=tool, tool_version=tool_version, scope=scope, mode=mode,
            effect_class=effect_class, status="BLOCKED", started_at=started_at,
            registry_version=registry_version, policy_version=policy_version,
            requested_by=requested_by, authority_context=authority_context, provenance=provenance,
            errors=[ToolError(code="AUTHORITY_TRANSFER_BLOCKED", message="authority transfer is forbidden")],
        )

    effect_policy = policy["effect_policy"]
    browser_network_admission = False
    if effect_class in effect_policy["network_effect_classes"]:
        try:
            browser_network_admission = browser_network_tool_admitted(tool, metadata)
        except BrowserConfigurationError as exc:
            return _receipt(
                request_id=request_id, tool=tool, tool_version=tool_version, scope=scope, mode=mode,
                effect_class=effect_class, status="BLOCKED", started_at=started_at,
                registry_version=registry_version, policy_version=policy_version,
                requested_by=requested_by, authority_context=authority_context, provenance=provenance,
                errors=[ToolError(code="BROWSER_CONFIGURATION_INVALID", message=str(exc))],
            )
        if policy["external_network_effects_enabled"] is False and not browser_network_admission:
            return _receipt(
                request_id=request_id, tool=tool, tool_version=tool_version, scope=scope, mode=mode,
                effect_class=effect_class, status="BLOCKED", started_at=started_at,
                registry_version=registry_version, policy_version=policy_version,
                requested_by=requested_by, authority_context=authority_context, provenance=provenance,
                errors=[ToolError(code="EXTERNAL_EFFECT_BLOCKED", message=f"network effect class is disabled: {effect_class}")],
            )
    if effect_class not in effect_policy["allowed_effect_classes"] and not browser_network_admission:
        return _receipt(
            request_id=request_id, tool=tool, tool_version=tool_version, scope=scope, mode=mode,
            effect_class=effect_class, status="BLOCKED", started_at=started_at,
            registry_version=registry_version, policy_version=policy_version,
            requested_by=requested_by, authority_context=authority_context, provenance=provenance,
            errors=[ToolError(code="EFFECT_CLASS_BLOCKED", message=f"policy does not admit effect class: {effect_class}")],
        )

    if mode == "WRITE":
        approval_error = _write_approval_error(authority_context, tool=tool, scope=scope)
        if approval_error is not None:
            return _receipt(
                request_id=request_id, tool=tool, tool_version=tool_version, scope=scope, mode=mode,
                effect_class=effect_class, status="APPROVAL_REQUIRED", started_at=started_at,
                registry_version=registry_version, policy_version=policy_version,
                requested_by=requested_by, authority_context=authority_context, provenance=provenance,
                errors=[approval_error],
            )

    handler_payload = dict(payload)
    if tool in {"browser.mutate.request", "browser.mutate.reversible", "browser.upload.execute"}:
        try:
            handler_payload["_aios_mutation_grant"] = build_mutation_grant(
                request_id=request_id,
                tool=tool,
                scope=scope,
                effect_class=effect_class,
                payload=payload,
                authority_context=authority_context,
            )
        except (MutationPolicyError, SessionCapturePolicyError) as exc:
            approval_codes = {
                "APPROVAL_REQUIRED",
                "APPROVAL_INVALID",
                "APPROVAL_EXPIRED",
                "APPROVAL_SCOPE_MISMATCH",
                "APPROVAL_TARGET_MISMATCH",
                "APPROVAL_METHOD_MISMATCH",
                "APPROVAL_IDEMPOTENCY_MISMATCH",
            }
            return _receipt(
                request_id=request_id, tool=tool, tool_version=tool_version, scope=scope, mode=mode,
                effect_class=effect_class,
                status="APPROVAL_REQUIRED" if exc.code in approval_codes else "BLOCKED",
                started_at=started_at, registry_version=registry_version, policy_version=policy_version,
                requested_by=requested_by, authority_context=authority_context, provenance=provenance,
                errors=[ToolError(code=exc.code, message=str(exc))],
            )

    if tool == "browser.session.capture":
        try:
            handler_payload["_aios_session_capture_grant"] = build_session_capture_grant(
                request_id=request_id,
                tool=tool,
                scope=scope,
                effect_class=effect_class,
                payload=payload,
                authority_context=authority_context,
            )
        except SessionCapturePolicyError as exc:
            approval_codes = {
                "APPROVAL_REQUIRED",
                "APPROVAL_INVALID",
                "APPROVAL_EXPIRED",
                "APPROVAL_SCOPE_MISMATCH",
            }
            return _receipt(
                request_id=request_id, tool=tool, tool_version=tool_version, scope=scope, mode=mode,
                effect_class=effect_class,
                status="APPROVAL_REQUIRED" if exc.code in approval_codes else "BLOCKED",
                started_at=started_at, registry_version=registry_version, policy_version=policy_version,
                requested_by=requested_by, authority_context=authority_context, provenance=provenance,
                errors=[ToolError(code=exc.code, message=str(exc))],
            )

    handler = HANDLERS.get(tool)
    if handler is None:
        return _receipt(
            request_id=request_id, tool=tool, tool_version=tool_version, scope=scope, mode=mode,
            effect_class=effect_class, status="BLOCKED", started_at=started_at,
            registry_version=registry_version, policy_version=policy_version,
            requested_by=requested_by, authority_context=authority_context, provenance=provenance,
            errors=[ToolError(code="HANDLER_NOT_REGISTERED", message=f"No handler is bound for {tool}")],
        )

    trust_binding_receipt: dict[str, Any] = {}
    trust_activation = policy["execution_trust_binding"]
    if tool in trust_activation["enforced_tools"]:
        try:
            trust_binding = build_runtime_system_health_binding(
                request_id=request_id,
                scope_key=scope,
                requested_by=requested_by,
                activation=trust_activation,
            )
            if trust_binding["catalog_state"]["catalog_revision"] != registry_version:
                trust_binding["invalidation_events"].append("tool.catalog.changed")
            if trust_binding["policy_state"]["policy_version"] != policy_version:
                trust_binding["invalidation_events"].append("tool.policy.changed")
            trust_binding_receipt = evaluate_trust_binding(trust_binding)
        except Exception:
            trust_binding_receipt = evaluate_trust_binding({"schema": "runtime-binding-failed"})
        if trust_binding_receipt.get("trust_decision") != trust_activation["required_decision"]:
            return _receipt(
                request_id=request_id, tool=tool, tool_version=tool_version, scope=scope, mode=mode,
                effect_class=effect_class, status="BLOCKED", started_at=started_at,
                registry_version=registry_version, policy_version=policy_version,
                requested_by=requested_by, authority_context=authority_context, provenance=provenance,
                errors=[ToolError(
                    code="TRUST_BINDING_BLOCKED",
                    message="active execution trust binding did not admit this invocation",
                    details={"reason_codes": trust_binding_receipt.get("reason_codes", [])},
                )],
                trust_binding_receipt=trust_binding_receipt,
            )

    try:
        output = handler(handler_payload)
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
                    "effect_policy": policy["effect_policy"],
                    "execution_trust_binding": policy["execution_trust_binding"],
                },
            }
        status = "COMPLETED"
        errors: list[ToolError] = []
    except MutationPolicyError as exc:
        output = {}
        status = "APPROVAL_REQUIRED" if exc.code.startswith("APPROVAL_") else "BLOCKED"
        errors = [ToolError(code=exc.code, message=str(exc))]
    except (TypeError, ValueError) as exc:
        output = {}
        status = "FAILED"
        errors = [ToolError(code="INVALID_INPUT", message=str(exc))]
    except Exception as exc:
        code = getattr(exc, "code", None)
        output = {}
        if isinstance(code, str):
            status = "BLOCKED" if code.endswith("_BLOCKED") or code in {"TARGET_BLOCKED", "UPLOAD_BLOCKED"} else "FAILED"
            errors = [ToolError(code=code, message=str(exc))]
        else:
            status = "FAILED"
            errors = [ToolError(code="INTERNAL_ERROR", message="tool execution failed unexpectedly")]

    external_effects = _browser_external_effects(tool, effect_class, output)
    return _receipt(
        request_id=request_id, tool=tool, tool_version=tool_version, scope=scope, mode=mode,
        effect_class=effect_class, status=status, started_at=started_at,
        registry_version=registry_version, policy_version=policy_version,
        requested_by=requested_by, authority_context=authority_context, output=output,
        errors=errors, provenance=provenance, handler_invoked=True,
        external_effects=external_effects,
        trust_binding_receipt=trust_binding_receipt,
    )
