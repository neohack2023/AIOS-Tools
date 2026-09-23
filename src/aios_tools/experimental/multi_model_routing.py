from __future__ import annotations

from dataclasses import asdict, dataclass
from enum import Enum

from aios_tools.canonical import canonical_sha256


RECEIPT_SCHEMA = "multi-model-routing/v1"


class RouteDecision(str, Enum):
    PASS = "PASS"
    BLOCK = "BLOCK"
    STALE = "STALE"
    DEGRADED = "DEGRADED"


@dataclass(frozen=True)
class RoutingObservation:
    routing_policy_version: str
    current_routing_policy_version: str
    workflow_pattern: str
    routing_objective_tier: str
    resolved_model: str | None
    model_available: bool
    fallback_declared: bool
    fallback_model: str | None
    critic_present: bool
    critic_model: str | None
    critic_read_only: bool
    critic_independence_proven: bool
    expected_leg_count: int
    leg_receipt_ids: tuple[str, ...]
    leg_costs: tuple[float, ...]
    cancelled: bool
    partial_patch_applied: bool
    final_patch_digest: str | None = None


@dataclass(frozen=True)
class RoutingReceipt:
    schema: str
    receipt_id: str
    decision: RouteDecision
    reason: str
    observation_digest: str
    authority_transfer: bool = False


def evaluate_routing(observation: RoutingObservation) -> RoutingReceipt:
    for value, code in (
        (observation.routing_policy_version, "routing_policy_version_required"),
        (
            observation.current_routing_policy_version,
            "current_routing_policy_version_required",
        ),
        (observation.workflow_pattern, "workflow_pattern_required"),
        (observation.routing_objective_tier, "routing_objective_tier_required"),
    ):
        if not isinstance(value, str) or not value.strip():
            raise ValueError(code)

    if observation.expected_leg_count < 1:
        raise ValueError("expected_leg_count_invalid")
    if any(cost < 0 for cost in observation.leg_costs):
        raise ValueError("negative_leg_cost")

    if (
        observation.routing_policy_version
        != observation.current_routing_policy_version
    ):
        decision = RouteDecision.STALE
        reason = "routing_policy_drift"
    elif observation.cancelled and observation.partial_patch_applied:
        decision = RouteDecision.BLOCK
        reason = "cancelled_workflow_leaked_partial_patch"
    elif observation.resolved_model is None:
        decision = RouteDecision.BLOCK
        reason = "resolved_model_missing"
    elif observation.critic_present and not observation.critic_read_only:
        decision = RouteDecision.BLOCK
        reason = "critic_write_boundary_violated"
    elif observation.critic_present and not observation.critic_independence_proven:
        decision = RouteDecision.BLOCK
        reason = "critic_independence_unproven"
    elif len(observation.leg_receipt_ids) != observation.expected_leg_count:
        decision = RouteDecision.BLOCK
        reason = "leg_receipt_accounting_incomplete"
    elif len(observation.leg_costs) != observation.expected_leg_count:
        decision = RouteDecision.BLOCK
        reason = "leg_cost_accounting_incomplete"
    elif not observation.model_available and not observation.fallback_declared:
        decision = RouteDecision.BLOCK
        reason = "model_unavailable_without_declared_fallback"
    elif not observation.model_available and observation.fallback_declared:
        if not observation.fallback_model:
            decision = RouteDecision.BLOCK
            reason = "fallback_model_identity_missing"
        else:
            decision = RouteDecision.DEGRADED
            reason = "declared_fallback_used"
    else:
        decision = RouteDecision.PASS
        reason = "routing_evidence_complete"

    payload = {
        **asdict(observation),
        "leg_receipt_ids": list(observation.leg_receipt_ids),
        "leg_costs": list(observation.leg_costs),
    }
    digest = canonical_sha256(payload)
    unsigned = {
        "schema": RECEIPT_SCHEMA,
        "decision": decision.value,
        "reason": reason,
        "observation_digest": digest,
        "authority_transfer": False,
    }
    return RoutingReceipt(
        schema=RECEIPT_SCHEMA,
        receipt_id="mmr_" + canonical_sha256(unsigned),
        decision=decision,
        reason=reason,
        observation_digest=digest,
        authority_transfer=False,
    )
