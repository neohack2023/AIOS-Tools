import pytest

from aios_tools.experimental.non_atomic_tool_retry import (
    AckState,
    CompositeState,
    DispatchState,
    PostconditionState,
    RetryDecision,
    RetryDecisionError,
    RetryObservation,
    decide_retry,
)


SCOPE = "scope-123"


def obs(**overrides):
    values = {
        "operation_id": "op-1",
        "prepared_scope_digest": SCOPE,
        "current_scope_digest": SCOPE,
        "dispatch_state": DispatchState.DISPATCHED,
        "ack_state": AckState.ACK_AMBIGUOUS,
        "postcondition_state": PostconditionState.VERIFY_UNKNOWN,
        "retry_policy_allows": True,
        "provider_idempotency_safe": False,
        "composite_state": CompositeState.NOT_APPLICABLE,
        "bounded_repair_available": False,
    }
    values.update(overrides)
    return RetryObservation(**values)


@pytest.mark.parametrize(
    ("observation", "expected"),
    [
        (
            obs(
                dispatch_state=DispatchState.NOT_DISPATCHED,
                postcondition_state=PostconditionState.NOT_CHECKED,
            ),
            RetryDecision.RETRY,
        ),
        (
            obs(postcondition_state=PostconditionState.EFFECT_CONFIRMED),
            RetryDecision.COMPLETE_NO_RETRY,
        ),
        (
            obs(postcondition_state=PostconditionState.VERIFY_UNKNOWN),
            RetryDecision.BLOCK,
        ),
        (
            obs(postcondition_state=PostconditionState.PARTIAL_EFFECT),
            RetryDecision.BLOCK,
        ),
        (
            obs(
                postcondition_state=PostconditionState.VERIFY_UNKNOWN,
                provider_idempotency_safe=True,
            ),
            RetryDecision.RETRY,
        ),
        (
            obs(
                postcondition_state=PostconditionState.VERIFY_UNKNOWN,
                retry_policy_allows=False,
            ),
            RetryDecision.BLOCK,
        ),
        (
            obs(
                postcondition_state=PostconditionState.EFFECT_CONFIRMED,
                composite_state=CompositeState.PARTIAL,
            ),
            RetryDecision.BLOCK,
        ),
        (
            obs(
                postcondition_state=PostconditionState.EFFECT_CONFIRMED,
                composite_state=CompositeState.RELATIONSHIP_MISMATCH,
            ),
            RetryDecision.BLOCK,
        ),
        (
            obs(
                postcondition_state=PostconditionState.EFFECT_CONFIRMED,
                composite_state=CompositeState.COMPLETE,
            ),
            RetryDecision.COMPLETE_NO_RETRY,
        ),
        (
            obs(
                postcondition_state=PostconditionState.PARTIAL_EFFECT,
                bounded_repair_available=True,
            ),
            RetryDecision.REPAIR_ONLY,
        ),
    ],
)
def test_sealed_retry_fixtures(observation, expected):
    assert decide_retry(observation).decision == expected


def test_ambiguous_ack_never_directly_becomes_success_without_verification():
    receipt = decide_retry(
        obs(postcondition_state=PostconditionState.VERIFY_UNKNOWN)
    )
    assert receipt.decision == RetryDecision.BLOCK


def test_scope_change_fails_closed():
    with pytest.raises(
        RetryDecisionError,
        match="recovery_scope_widening_forbidden",
    ):
        decide_retry(obs(current_scope_digest="different-scope"))


def test_same_observation_produces_same_receipt():
    first = decide_retry(
        obs(postcondition_state=PostconditionState.EFFECT_CONFIRMED)
    )
    second = decide_retry(
        obs(postcondition_state=PostconditionState.EFFECT_CONFIRMED)
    )
    assert first == second


def test_operation_change_changes_receipt_identity():
    first = decide_retry(
        obs(postcondition_state=PostconditionState.EFFECT_CONFIRMED)
    )
    second = decide_retry(
        obs(
            operation_id="op-2",
            postcondition_state=PostconditionState.EFFECT_CONFIRMED,
        )
    )
    assert first.receipt_id != second.receipt_id


def test_failed_before_effect_allows_retry():
    receipt = decide_retry(
        obs(
            ack_state=AckState.FAILED_BEFORE_EFFECT,
            postcondition_state=PostconditionState.EFFECT_ABSENT,
        )
    )
    assert receipt.decision == RetryDecision.RETRY
