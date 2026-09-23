from __future__ import annotations

from dataclasses import asdict, dataclass
from enum import Enum

from aios_tools.canonical import canonical_sha256


RECEIPT_SCHEMA = "programmatic-tool-boundary/v1"


class ToolBoundaryError(RuntimeError):
    pass


class EffectClass(str, Enum):
    READ = "READ"
    WRITE = "WRITE"
    DESTRUCTIVE = "DESTRUCTIVE"


class ChildVerdict(str, Enum):
    PASS = "PASS"
    BLOCK = "BLOCK"
    NON_SUCCESS = "NON_SUCCESS"


_EFFECT_RANK = {
    EffectClass.READ: 0,
    EffectClass.WRITE: 1,
    EffectClass.DESTRUCTIVE: 2,
}


@dataclass(frozen=True)
class ChildCallObservation:
    parent_execution_id: str
    child_call_id: str
    child_order: int
    tool_id: str
    allowed_tool_ids: tuple[str, ...]
    scope_key: str
    parent_scope_key: str
    effect_class: EffectClass
    parent_max_effect_class: EffectClass
    parameter_digest: str
    policy_id: str
    policy_version: str
    policy_evaluated: bool
    attributed: bool
    duplicate_non_idempotent_effect: bool = False


@dataclass(frozen=True)
class ChildCallReceipt:
    schema: str
    receipt_id: str
    child_call_id: str
    verdict: ChildVerdict
    reason: str
    observation_digest: str
    authority_transfer: bool = False


def evaluate_child_call(observation: ChildCallObservation) -> ChildCallReceipt:
    for value, code in (
        (observation.parent_execution_id, "parent_execution_id_required"),
        (observation.child_call_id, "child_call_id_required"),
        (observation.tool_id, "tool_id_required"),
        (observation.scope_key, "scope_key_required"),
        (observation.parent_scope_key, "parent_scope_key_required"),
        (observation.parameter_digest, "parameter_digest_required"),
        (observation.policy_id, "policy_id_required"),
        (observation.policy_version, "policy_version_required"),
    ):
        if not isinstance(value, str) or not value.strip():
            raise ToolBoundaryError(code)

    if observation.child_order < 0:
        raise ToolBoundaryError("child_order_invalid")
    if observation.tool_id not in observation.allowed_tool_ids:
        verdict = ChildVerdict.BLOCK
        reason = "unlisted_tool"
    elif observation.scope_key != observation.parent_scope_key:
        verdict = ChildVerdict.BLOCK
        reason = "scope_widening"
    elif _EFFECT_RANK[observation.effect_class] > _EFFECT_RANK[
        observation.parent_max_effect_class
    ]:
        verdict = ChildVerdict.BLOCK
        reason = "effect_authority_widening"
    elif not observation.attributed:
        verdict = ChildVerdict.NON_SUCCESS
        reason = "child_attribution_missing"
    elif not observation.policy_evaluated:
        verdict = ChildVerdict.NON_SUCCESS
        reason = "child_policy_not_evaluated"
    elif observation.duplicate_non_idempotent_effect:
        verdict = ChildVerdict.NON_SUCCESS
        reason = "duplicate_non_idempotent_effect"
    else:
        verdict = ChildVerdict.PASS
        reason = "child_call_legal"

    payload = {
        **asdict(observation),
        "allowed_tool_ids": list(observation.allowed_tool_ids),
        "effect_class": observation.effect_class.value,
        "parent_max_effect_class": observation.parent_max_effect_class.value,
    }
    observation_digest = canonical_sha256(payload)
    unsigned = {
        "schema": RECEIPT_SCHEMA,
        "child_call_id": observation.child_call_id,
        "verdict": verdict.value,
        "reason": reason,
        "observation_digest": observation_digest,
        "authority_transfer": False,
    }
    return ChildCallReceipt(
        schema=RECEIPT_SCHEMA,
        receipt_id="ptb_" + canonical_sha256(unsigned),
        child_call_id=observation.child_call_id,
        verdict=verdict,
        reason=reason,
        observation_digest=observation_digest,
        authority_transfer=False,
    )


def evaluate_program_run(
    observations: tuple[ChildCallObservation, ...],
) -> tuple[ChildCallReceipt, ...]:
    seen_ids: set[str] = set()
    receipts: list[ChildCallReceipt] = []
    for observation in sorted(observations, key=lambda item: item.child_order):
        if observation.child_call_id in seen_ids:
            raise ToolBoundaryError("duplicate_child_call_id")
        seen_ids.add(observation.child_call_id)
        receipts.append(evaluate_child_call(observation))
    return tuple(receipts)
