from __future__ import annotations

from dataclasses import asdict, dataclass
from enum import Enum

from aios_tools.canonical import canonical_sha256


RECEIPT_SCHEMA = "non-atomic-tool-retry-decision/v1"


class RetryDecisionError(RuntimeError):
    pass


class DispatchState(str, Enum):
    NOT_DISPATCHED = "NOT_DISPATCHED"
    DISPATCHED = "DISPATCHED"


class AckState(str, Enum):
    ACK_CONFIRMED = "ACK_CONFIRMED"
    ACK_AMBIGUOUS = "ACK_AMBIGUOUS"
    FAILED_BEFORE_EFFECT = "FAILED_BEFORE_EFFECT"


class PostconditionState(str, Enum):
    NOT_CHECKED = "NOT_CHECKED"
    EFFECT_CONFIRMED = "EFFECT_CONFIRMED"
    EFFECT_ABSENT = "EFFECT_ABSENT"
    VERIFY_UNKNOWN = "VERIFY_UNKNOWN"
    PARTIAL_EFFECT = "PARTIAL_EFFECT"


class CompositeState(str, Enum):
    NOT_APPLICABLE = "NOT_APPLICABLE"
    COMPLETE = "COMPLETE"
    PARTIAL = "PARTIAL"
    RELATIONSHIP_MISMATCH = "RELATIONSHIP_MISMATCH"


class RetryDecision(str, Enum):
    COMPLETE_NO_RETRY = "COMPLETE_NO_RETRY"
    RETRY = "RETRY"
    REPAIR_ONLY = "REPAIR_ONLY"
    BLOCK = "BLOCK"


@dataclass(frozen=True)
class RetryObservation:
    operation_id: str
    prepared_scope_digest: str
    current_scope_digest: str
    dispatch_state: DispatchState
    ack_state: AckState
    postcondition_state: PostconditionState
    retry_policy_allows: bool = True
    provider_idempotency_safe: bool = False
    composite_state: CompositeState = CompositeState.NOT_APPLICABLE
    bounded_repair_available: bool = False


@dataclass(frozen=True)
class RetryDecisionReceipt:
    schema: str
    receipt_id: str
    operation_id: str
    decision: RetryDecision
    reason: str
    observation_digest: str
    prepared_scope_digest: str
    current_scope_digest: str


def _validate(observation: RetryObservation) -> None:
    if not observation.operation_id.strip():
        raise RetryDecisionError("operation_id_required")
    if not observation.prepared_scope_digest.strip():
        raise RetryDecisionError("prepared_scope_digest_required")
    if not observation.current_scope_digest.strip():
        raise RetryDecisionError("current_scope_digest_required")
    if observation.prepared_scope_digest != observation.current_scope_digest:
        raise RetryDecisionError("recovery_scope_widening_forbidden")

    if (
        observation.dispatch_state == DispatchState.NOT_DISPATCHED
        and observation.postcondition_state
        not in (PostconditionState.NOT_CHECKED, PostconditionState.EFFECT_ABSENT)
    ):
        raise RetryDecisionError("undispatched_effect_observation_invalid")


def decide_retry(observation: RetryObservation) -> RetryDecisionReceipt:
    _validate(observation)

    if observation.dispatch_state == DispatchState.NOT_DISPATCHED:
        decision = (
            RetryDecision.RETRY
            if observation.retry_policy_allows
            else RetryDecision.BLOCK
        )
        reason = "not_dispatched"

    elif observation.ack_state == AckState.FAILED_BEFORE_EFFECT:
        decision = (
            RetryDecision.RETRY
            if observation.retry_policy_allows
            else RetryDecision.BLOCK
        )
        reason = "failed_before_effect"

    elif observation.ack_state == AckState.ACK_CONFIRMED:
        if observation.postcondition_state == PostconditionState.PARTIAL_EFFECT:
            decision = (
                RetryDecision.REPAIR_ONLY
                if observation.bounded_repair_available
                else RetryDecision.BLOCK
            )
            reason = "partial_effect"
        elif observation.composite_state in (
            CompositeState.PARTIAL,
            CompositeState.RELATIONSHIP_MISMATCH,
        ):
            decision = (
                RetryDecision.REPAIR_ONLY
                if observation.bounded_repair_available
                else RetryDecision.BLOCK
            )
            reason = "composite_postcondition_failed"
        else:
            decision = RetryDecision.COMPLETE_NO_RETRY
            reason = "ack_confirmed"

    else:
        # ACK_AMBIGUOUS must pass through postcondition verification.
        if observation.postcondition_state == PostconditionState.EFFECT_CONFIRMED:
            if observation.composite_state in (
                CompositeState.PARTIAL,
                CompositeState.RELATIONSHIP_MISMATCH,
            ):
                decision = (
                    RetryDecision.REPAIR_ONLY
                    if observation.bounded_repair_available
                    else RetryDecision.BLOCK
                )
                reason = "composite_postcondition_failed"
            else:
                decision = RetryDecision.COMPLETE_NO_RETRY
                reason = "effect_confirmed_after_ambiguous_ack"

        elif observation.postcondition_state == PostconditionState.EFFECT_ABSENT:
            if observation.retry_policy_allows:
                decision = RetryDecision.RETRY
                reason = "effect_absent"
            elif observation.provider_idempotency_safe:
                decision = RetryDecision.RETRY
                reason = "provider_idempotency_allows_replay"
            else:
                decision = RetryDecision.BLOCK
                reason = "retry_policy_denied"

        elif observation.postcondition_state == PostconditionState.PARTIAL_EFFECT:
            decision = (
                RetryDecision.REPAIR_ONLY
                if observation.bounded_repair_available
                else RetryDecision.BLOCK
            )
            reason = "partial_effect"

        elif (
            observation.provider_idempotency_safe
            and observation.retry_policy_allows
            and observation.postcondition_state == PostconditionState.VERIFY_UNKNOWN
        ):
            decision = RetryDecision.RETRY
            reason = "provider_idempotency_allows_replay"

        else:
            decision = RetryDecision.BLOCK
            reason = "verification_inconclusive"

    observation_payload = {
        **asdict(observation),
        "dispatch_state": observation.dispatch_state.value,
        "ack_state": observation.ack_state.value,
        "postcondition_state": observation.postcondition_state.value,
        "composite_state": observation.composite_state.value,
    }
    observation_digest = canonical_sha256(observation_payload)

    unsigned = {
        "schema": RECEIPT_SCHEMA,
        "operation_id": observation.operation_id,
        "decision": decision.value,
        "reason": reason,
        "observation_digest": observation_digest,
        "prepared_scope_digest": observation.prepared_scope_digest,
        "current_scope_digest": observation.current_scope_digest,
    }
    receipt_id = "natr_" + canonical_sha256(unsigned)

    return RetryDecisionReceipt(
        schema=RECEIPT_SCHEMA,
        receipt_id=receipt_id,
        operation_id=observation.operation_id,
        decision=decision,
        reason=reason,
        observation_digest=observation_digest,
        prepared_scope_digest=observation.prepared_scope_digest,
        current_scope_digest=observation.current_scope_digest,
    )
