from __future__ import annotations

from dataclasses import asdict, dataclass
from enum import Enum

from aios_tools.canonical import canonical_sha256


RECEIPT_SCHEMA = "responses-gateway-compatibility/v1"


class CompatibilityDecision(str, Enum):
    PASS = "PASS"
    BLOCK = "BLOCK"
    STALE = "STALE"


class ToolExecutionLocation(str, Enum):
    CALLER_LOCAL = "CALLER_LOCAL"
    GATEWAY = "GATEWAY"
    UPSTREAM_PROVIDER = "UPSTREAM_PROVIDER"
    UNKNOWN = "UNKNOWN"


@dataclass(frozen=True)
class GatewayCompatibilityObservation:
    gateway_version: str
    gateway_image_digest: str
    wire_api: str
    model_alias: str
    upstream_model_binding: str
    expected_upstream_model_binding: str
    caller_identity: str
    caller_identity_preserved: bool
    budget_policy_id: str
    rate_policy_id: str
    policy_rejection_visible: bool
    previous_response_id_supported: bool
    semantic_continuation_verified: bool
    stream_completed_event_observed: bool
    function_call_id: str | None
    function_call_id_stable: bool
    tool_execution_location: ToolExecutionLocation
    gateway_trace_id: str


@dataclass(frozen=True)
class GatewayCompatibilityReceipt:
    schema: str
    receipt_id: str
    decision: CompatibilityDecision
    reason: str
    observation_digest: str
    authority_transfer: bool = False


def evaluate_gateway_compatibility(
    observation: GatewayCompatibilityObservation,
) -> GatewayCompatibilityReceipt:
    for value, code in (
        (observation.gateway_version, "gateway_version_required"),
        (observation.gateway_image_digest, "gateway_image_digest_required"),
        (observation.wire_api, "wire_api_required"),
        (observation.model_alias, "model_alias_required"),
        (observation.upstream_model_binding, "upstream_model_binding_required"),
        (
            observation.expected_upstream_model_binding,
            "expected_upstream_model_binding_required",
        ),
        (observation.caller_identity, "caller_identity_required"),
        (observation.budget_policy_id, "budget_policy_id_required"),
        (observation.rate_policy_id, "rate_policy_id_required"),
        (observation.gateway_trace_id, "gateway_trace_id_required"),
    ):
        if not isinstance(value, str) or not value.strip():
            raise ValueError(code)

    if (
        observation.upstream_model_binding
        != observation.expected_upstream_model_binding
    ):
        decision = CompatibilityDecision.STALE
        reason = "model_alias_binding_changed"
    elif observation.wire_api.lower() != "responses":
        decision = CompatibilityDecision.BLOCK
        reason = "responses_wire_contract_missing"
    elif not observation.previous_response_id_supported:
        decision = CompatibilityDecision.BLOCK
        reason = "previous_response_id_unsupported"
    elif not observation.semantic_continuation_verified:
        decision = CompatibilityDecision.BLOCK
        reason = "continuation_semantics_failed"
    elif not observation.stream_completed_event_observed:
        decision = CompatibilityDecision.BLOCK
        reason = "stream_terminal_completion_missing"
    elif not observation.function_call_id or not observation.function_call_id_stable:
        decision = CompatibilityDecision.BLOCK
        reason = "function_call_identity_unstable"
    elif not observation.caller_identity_preserved:
        decision = CompatibilityDecision.BLOCK
        reason = "caller_identity_collapsed"
    elif not observation.policy_rejection_visible:
        decision = CompatibilityDecision.BLOCK
        reason = "budget_or_rate_rejection_not_attributable"
    elif observation.tool_execution_location != ToolExecutionLocation.CALLER_LOCAL:
        decision = CompatibilityDecision.BLOCK
        reason = "local_tool_authority_not_preserved"
    else:
        decision = CompatibilityDecision.PASS
        reason = "responses_gateway_contract_preserved"

    payload = {
        **asdict(observation),
        "tool_execution_location": observation.tool_execution_location.value,
    }
    digest = canonical_sha256(payload)
    unsigned = {
        "schema": RECEIPT_SCHEMA,
        "decision": decision.value,
        "reason": reason,
        "observation_digest": digest,
        "authority_transfer": False,
    }
    return GatewayCompatibilityReceipt(
        schema=RECEIPT_SCHEMA,
        receipt_id="rgc_" + canonical_sha256(unsigned),
        decision=decision,
        reason=reason,
        observation_digest=digest,
        authority_transfer=False,
    )
