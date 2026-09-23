import pytest

from aios_tools.experimental.multi_model_routing import (
    RouteDecision,
    RoutingObservation,
    evaluate_routing,
)


def obs(**kwargs):
    values = dict(
        routing_policy_version="p1",
        current_routing_policy_version="p1",
        workflow_pattern="SINGLE_PATH",
        routing_objective_tier="balance",
        resolved_model="model-a",
        model_available=True,
        fallback_declared=True,
        fallback_model="model-b",
        critic_present=False,
        critic_model=None,
        critic_read_only=True,
        critic_independence_proven=True,
        expected_leg_count=1,
        leg_receipt_ids=("leg-1",),
        leg_costs=(1.0,),
        cancelled=False,
        partial_patch_applied=False,
        final_patch_digest="patch-1",
    )
    values.update(kwargs)
    return RoutingObservation(**values)


@pytest.mark.parametrize(
    ("candidate", "expected"),
    [
        (obs(), RouteDecision.PASS),
        (
            obs(
                workflow_pattern="CASCADE",
                expected_leg_count=2,
                leg_receipt_ids=("leg-1", "leg-2"),
                leg_costs=(1.0, 2.0),
            ),
            RouteDecision.PASS,
        ),
        (
            obs(
                critic_present=True,
                critic_model="critic",
                critic_read_only=False,
            ),
            RouteDecision.BLOCK,
        ),
        (
            obs(cancelled=True, partial_patch_applied=True),
            RouteDecision.BLOCK,
        ),
        (
            obs(model_available=False),
            RouteDecision.DEGRADED,
        ),
        (
            obs(
                model_available=False,
                fallback_declared=False,
                fallback_model=None,
            ),
            RouteDecision.BLOCK,
        ),
        (
            obs(leg_costs=()),
            RouteDecision.BLOCK,
        ),
        (
            obs(current_routing_policy_version="p2"),
            RouteDecision.STALE,
        ),
        (
            obs(resolved_model=None),
            RouteDecision.BLOCK,
        ),
        (
            obs(
                critic_present=True,
                critic_model="same-family",
                critic_independence_proven=False,
            ),
            RouteDecision.BLOCK,
        ),
    ],
)
def test_routing_matrix(candidate, expected):
    receipt = evaluate_routing(candidate)
    assert receipt.decision == expected
    assert receipt.authority_transfer is False


def test_objective_tier_never_substitutes_for_resolved_model():
    receipt = evaluate_routing(
        obs(
            routing_objective_tier="intelligence",
            resolved_model=None,
        )
    )
    assert receipt.decision == RouteDecision.BLOCK


def test_fallback_identity_is_required():
    receipt = evaluate_routing(
        obs(
            model_available=False,
            fallback_declared=True,
            fallback_model=None,
        )
    )
    assert receipt.decision == RouteDecision.BLOCK


def test_receipt_is_deterministic():
    candidate = obs()
    assert evaluate_routing(candidate) == evaluate_routing(candidate)
