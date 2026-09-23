import pytest

from aios_tools.experimental.daily_debrief_handoff import (
    HandoffError,
    HandoffNotReady,
    build_implementation_handoff,
    render_github_issue_draft,
    validate_implementation_handoff,
)
from aios_tools.experimental.daily_debrief_projection import (
    DailyDebriefProjectionState,
    ProjectionLineage,
)


def _ready_state():
    return DailyDebriefProjectionState(
        last_applied_sequence=3,
        processed_event_ids=["event-1", "event-2", "event-3"],
        lineages={
            "model-lifecycle": ProjectionLineage(
                lineage="model-lifecycle",
                first_seen="2026-09-21",
                last_seen="2026-09-23",
                event_ids=["event-1", "event-2", "event-3"],
                source_ids=[
                    "2026-09-21::google_drive::source-a::rev-a",
                    "2026-09-22::google_drive::source-b::rev-b",
                    "2026-09-23::google_drive::source-c::rev-c",
                ],
                dispositions=["REFINEMENT"],
                implementation_consequences=[
                    "Invalidate verification when model identity changes."
                ],
                remaining_test_ids=[],
                resolved_test_ids=["model-lifecycle.live-verification"],
                simulation_pass_count=2,
                live_verified_count=1,
            )
        },
    )


def _build():
    return build_implementation_handoff(
        _ready_state(),
        lineage="model-lifecycle",
        scope_key="global-working-memory",
        repository="neohack2023/AIOS-Tools",
    )


def test_ready_lineage_produces_read_only_handoff():
    handoff = _build()
    assert handoff["candidate_state"] == "READY_FOR_IMPLEMENTATION_PLAN"
    assert handoff["handoff_id"].startswith("ddh_")
    assert handoff["evidence_count"] == 3
    assert handoff["distinct_debriefs"] == 3
    assert handoff["authority"]["read_only"] is True
    assert handoff["authority"]["human_submission_required"] is True
    assert handoff["authority"]["automatic_issue_creation"] is False
    assert handoff["authority"]["automatic_pr_creation"] is False
    assert handoff["authority"]["automatic_merge"] is False
    validate_implementation_handoff(handoff)


def test_same_state_produces_same_handoff_identity():
    assert _build() == _build()


def test_verification_required_lineage_cannot_handoff():
    state = _ready_state()
    lineage = state.lineages["model-lifecycle"]
    lineage.live_verified_count = 0
    lineage.remaining_test_ids = ["model-lifecycle.live-verification"]
    with pytest.raises(
        HandoffNotReady,
        match="handoff_live_verification_required",
    ):
        build_implementation_handoff(
            state,
            lineage="model-lifecycle",
            scope_key="global-working-memory",
            repository="neohack2023/AIOS-Tools",
        )


def test_single_day_repeat_does_not_satisfy_threshold():
    state = _ready_state()
    state.lineages["model-lifecycle"].source_ids = [
        "2026-09-21::google_drive::source-a::rev-a",
        "2026-09-21::google_drive::source-b::rev-b",
        "2026-09-21::google_drive::source-c::rev-c",
    ]
    with pytest.raises(
        HandoffNotReady,
        match="handoff_debrief_threshold_not_met",
    ):
        build_implementation_handoff(
            state,
            lineage="model-lifecycle",
            scope_key="global-working-memory",
            repository="neohack2023/AIOS-Tools",
        )


def test_tampered_handoff_fails_digest_validation():
    handoff = _build()
    handoff["repository"] = "other/repo"
    with pytest.raises(HandoffError, match="handoff_digest_mismatch"):
        validate_implementation_handoff(handoff)


def test_rehashed_authority_widening_still_fails():
    handoff = _build()
    handoff["authority"]["automatic_issue_creation"] = True
    from aios_tools.canonical import canonical_sha256
    unsigned = {
        key: value
        for key, value in handoff.items()
        if key != "handoff_id"
    }
    handoff["handoff_id"] = "ddh_" + canonical_sha256(unsigned)
    with pytest.raises(
        HandoffError,
        match="handoff_automatic_authority_forbidden",
    ):
        validate_implementation_handoff(handoff)


def test_issue_draft_renderer_links_existing_intake():
    draft = render_github_issue_draft(_build())
    assert draft["title"] == (
        "Implement Daily Debrief lineage: model-lifecycle"
    )
    assert "Parent intake: #74" in draft["body"]
    assert "read-only draft" in draft["body"]
    assert "does not create an issue" in draft["body"]


def test_invalid_repository_fails_closed():
    with pytest.raises(HandoffError, match="handoff_repository_invalid"):
        build_implementation_handoff(
            _ready_state(),
            lineage="model-lifecycle",
            scope_key="global-working-memory",
            repository="not-a-repository",
        )
