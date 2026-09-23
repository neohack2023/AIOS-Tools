import pytest

from aios_tools.experimental.resource_fallback_equivalence import (
    FallbackDecision,
    FallbackObservation,
    ResourceCandidate,
    select_prequalified_resource,
)


def candidate(
    resource_id,
    *,
    compatible=True,
    capacity=True,
    count=1,
    fingerprint=None,
):
    return ResourceCandidate(
        resource_id=resource_id,
        compatibility_receipt_id=(
            f"compat-{resource_id}" if compatible else None
        ),
        capacity_available=capacity,
        instance_count=count,
        environment_fingerprint=fingerprint or f"env-{resource_id}",
        cost_class="standard",
        performance_equivalence_class="declared-compatible",
    )


def observation(candidates, **kwargs):
    values = dict(
        preference_list_digest="list-a",
        validated_preference_list_digest="list-a",
        candidates=tuple(candidates),
        queue_deadline_open=True,
    )
    values.update(kwargs)
    return FallbackObservation(**values)


def test_selects_rank_two_when_rank_one_has_no_capacity():
    result = select_prequalified_resource(
        observation(
            (
                candidate("p5", capacity=False, count=2),
                candidate("p4", capacity=True, count=4),
            )
        )
    )
    assert result.decision == FallbackDecision.SELECT
    assert result.selected_resource_id == "p4"
    assert result.selection_rank == 2
    assert result.selected_instance_count == 4


def test_incompatible_capacity_is_skipped():
    result = select_prequalified_resource(
        observation(
            (
                candidate("bad", compatible=False, capacity=True),
                candidate("good", compatible=True, capacity=True),
            )
        )
    )
    assert result.decision == FallbackDecision.SELECT
    assert result.selected_resource_id == "good"
    assert result.selection_rank == 2


def test_list_change_invalidates_prior_validation():
    result = select_prequalified_resource(
        observation(
            (candidate("good"),),
            preference_list_digest="new-list",
        )
    )
    assert result.decision == FallbackDecision.STALE_LIST


def test_queue_expiry_does_not_widen_resource_set():
    result = select_prequalified_resource(
        observation(
            (candidate("good", capacity=False),),
            queue_deadline_open=False,
        )
    )
    assert result.decision == FallbackDecision.QUEUE_EXPIRED


def test_no_compatible_capacity_fails_boundedly():
    result = select_prequalified_resource(
        observation(
            (
                candidate("bad", compatible=False, capacity=True),
                candidate("good", compatible=True, capacity=False),
            )
        )
    )
    assert result.decision == FallbackDecision.NO_COMPATIBLE_CAPACITY
    assert result.selected_resource_id is None


def test_environment_identity_is_preserved():
    result = select_prequalified_resource(
        observation(
            (
                candidate("g6", capacity=False, fingerprint="env-g6"),
                candidate("g5", capacity=True, fingerprint="env-g5"),
            )
        )
    )
    assert result.selected_environment_fingerprint == "env-g5"


def test_duplicate_resource_id_fails_closed():
    with pytest.raises(ValueError, match="duplicate_resource_id"):
        select_prequalified_resource(
            observation((candidate("same"), candidate("same")))
        )


def test_receipt_is_deterministic():
    value = observation((candidate("good"),))
    assert select_prequalified_resource(value) == select_prequalified_resource(value)
