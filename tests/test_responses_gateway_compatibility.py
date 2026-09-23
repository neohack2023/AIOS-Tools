import pytest

from aios_tools.experimental.responses_gateway_compatibility import (
    CompatibilityDecision,
    GatewayCompatibilityObservation,
    ToolExecutionLocation,
    evaluate_gateway_compatibility,
)


def obs(**kwargs):
    values = dict(
        gateway_version="1.0",
        gateway_image_digest="image-digest",
        wire_api="responses",
        model_alias="coding-model",
        upstream_model_binding="provider/model-v1",
        expected_upstream_model_binding="provider/model-v1",
        caller_identity="user-1",
        caller_identity_preserved=True,
        budget_policy_id="budget-1",
        rate_policy_id="rate-1",
        policy_rejection_visible=True,
        previous_response_id_supported=True,
        semantic_continuation_verified=True,
        stream_completed_event_observed=True,
        function_call_id="call-1",
        function_call_id_stable=True,
        tool_execution_location=ToolExecutionLocation.CALLER_LOCAL,
        gateway_trace_id="trace-1",
    )
    values.update(kwargs)
    return GatewayCompatibilityObservation(**values)


@pytest.mark.parametrize(
    ("candidate", "expected"),
    [
        (obs(), CompatibilityDecision.PASS),
        (
            obs(wire_api="chat-completions"),
            CompatibilityDecision.BLOCK,
        ),
        (
            obs(semantic_continuation_verified=False),
            CompatibilityDecision.BLOCK,
        ),
        (
            obs(stream_completed_event_observed=False),
            CompatibilityDecision.BLOCK,
        ),
        (
            obs(function_call_id_stable=False),
            CompatibilityDecision.BLOCK,
        ),
        (
            obs(caller_identity_preserved=False),
            CompatibilityDecision.BLOCK,
        ),
        (
            obs(policy_rejection_visible=False),
            CompatibilityDecision.BLOCK,
        ),
        (
            obs(upstream_model_binding="provider/model-v2"),
            CompatibilityDecision.STALE,
        ),
        (
            obs(tool_execution_location=ToolExecutionLocation.GATEWAY),
            CompatibilityDecision.BLOCK,
        ),
    ],
)
def test_gateway_compatibility_matrix(candidate, expected):
    receipt = evaluate_gateway_compatibility(candidate)
    assert receipt.decision == expected
    assert receipt.authority_transfer is False


def test_previous_response_id_is_required():
    receipt = evaluate_gateway_compatibility(
        obs(previous_response_id_supported=False)
    )
    assert receipt.decision == CompatibilityDecision.BLOCK


def test_missing_function_call_id_blocks():
    receipt = evaluate_gateway_compatibility(obs(function_call_id=None))
    assert receipt.decision == CompatibilityDecision.BLOCK


def test_receipt_is_deterministic():
    candidate = obs()
    assert evaluate_gateway_compatibility(candidate) == evaluate_gateway_compatibility(candidate)
