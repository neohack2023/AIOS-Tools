from aios_tools.experimental.daily_debrief_digest import (
    DailyDebriefDigestState,
    DebriefFinding,
    build_implementation_plan,
    implementation_candidates,
    ingest_findings,
    state_from_dict,
    state_to_dict,
)


def _finding(date, source_id, lineage, title, consequence, validation="SIMULATION 5/5 PASS", remaining=None, resolved=()):
    return DebriefFinding(
        source_id=source_id,
        debrief_date=date,
        lineage=lineage,
        title=title,
        disposition="REFINEMENT",
        confidence="high",
        implementation_consequence=consequence,
        validation_state=validation,
        remaining_test=remaining,
        resolved_tests=resolved,
    )


def test_exact_replay_is_idempotent():
    state = DailyDebriefDigestState()
    finding = _finding("2026-09-21", "a", "model-lifecycle", "A", "Consequence A")
    ingest_findings(state, [finding, finding])
    assert len(state.processed_evidence_digests) == 1


def test_repeated_lineage_across_days_becomes_plan_candidate():
    state = DailyDebriefDigestState()
    ingest_findings(state, [
        _finding("2026-09-21", "a", "model-lifecycle", "A", "Consequence A", remaining="live-test-a"),
        _finding("2026-09-22", "b", "model-lifecycle", "B", "Consequence B", remaining="live-test-b"),
    ])
    candidate = implementation_candidates(state)[0]
    assert candidate.state == "PLAN_CANDIDATE_VERIFICATION_REQUIRED"
    assert candidate.distinct_debriefs == 2


def test_single_day_noise_does_not_form_plan():
    state = DailyDebriefDigestState()
    ingest_findings(state, [_finding("2026-09-22", "a", "one-off", "A", "Consequence A")])
    assert implementation_candidates(state) == []


def test_later_live_evidence_can_resolve_old_gate():
    state = DailyDebriefDigestState()
    ingest_findings(state, [
        _finding("2026-09-21", "a", "ci-mcp", "A", "Consequence A", remaining="replay-live"),
        _finding("2026-09-22", "b", "ci-mcp", "B", "Consequence B"),
        _finding("2026-09-23", "c", "ci-mcp", "C", "Consequence C", validation="LIVE PASS", resolved=("replay-live",)),
    ])
    candidate = implementation_candidates(state)[0]
    assert candidate.state == "READY_FOR_IMPLEMENTATION_PLAN"
    assert candidate.remaining_tests == ()


def test_state_round_trip_preserves_digest():
    state = DailyDebriefDigestState()
    ingest_findings(state, [
        _finding("2026-09-21", "a", "x", "A", "Consequence A", remaining="test-a"),
        _finding("2026-09-22", "b", "x", "B", "Consequence B"),
    ])
    restored = state_from_dict(state_to_dict(state))
    assert state_to_dict(restored) == state_to_dict(state)


def test_unknown_state_schema_fails_closed():
    try:
        state_from_dict({"schema": "future/v99"})
    except ValueError as exc:
        assert str(exc) == "unsupported_digest_state_schema"
    else:
        raise AssertionError("expected ValueError")


def test_plan_preserves_authority_boundary():
    state = DailyDebriefDigestState()
    ingest_findings(state, [
        _finding("2026-09-21", "a", "x", "A", "Consequence A"),
        _finding("2026-09-22", "b", "x", "B", "Consequence B"),
    ])
    plan = build_implementation_plan(state)
    assert plan["authority"]["research_is_evidence_not_canon"] is True
    assert plan["authority"]["automatic_runtime_activation"] is False
    assert plan["authority"]["automatic_repository_mutation"] is False


def test_distinct_debrief_count_uses_date_not_source_count():
    state = DailyDebriefDigestState()
    ingest_findings(state, [
        _finding("2026-09-21", "a", "x", "A", "Consequence A"),
        _finding("2026-09-21", "b", "x", "B", "Consequence B"),
    ])
    assert implementation_candidates(state) == []
