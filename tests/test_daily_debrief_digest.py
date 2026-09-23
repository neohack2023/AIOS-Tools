from aios_tools.experimental.daily_debrief_digest import (
    DailyDebriefDigestState,
    DebriefFinding,
    build_implementation_plan,
    implementation_candidates,
    ingest_findings,
)


def _finding(date, source_id, lineage, title, consequence, validation="SIMULATION 5/5 PASS", remaining=None):
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
    )


def test_exact_replay_is_idempotent():
    state = DailyDebriefDigestState()
    finding = _finding(
        "2026-09-21",
        "copilot-model-deprecation",
        "model-lifecycle",
        "Copilot model deprecations",
        "Invalidate verification when bound model changes.",
    )
    ingest_findings(state, [finding, finding])
    assert len(state.processed_evidence_digests) == 1
    assert len(state.lineages["model-lifecycle"].evidence_digests) == 1


def test_repeated_lineage_across_days_becomes_plan_candidate():
    state = DailyDebriefDigestState()
    ingest_findings(
        state,
        [
            _finding(
                "2026-09-21",
                "copilot-model-deprecation",
                "model-lifecycle",
                "Copilot model deprecations",
                "Invalidate historical verification on model substitution or deprecation.",
                remaining="Freeze prompts against retiring and replacement models.",
            ),
            _finding(
                "2026-09-22",
                "grok-4-7-copilot",
                "model-lifecycle",
                "Grok 4.7 in Copilot",
                "Add new models only as lifecycle benchmark candidates until verified.",
                remaining="Run bounded benchmark under the existing staleness gate.",
            ),
        ],
    )
    candidates = implementation_candidates(state)
    assert len(candidates) == 1
    assert candidates[0].lineage == "model-lifecycle"
    assert candidates[0].state == "PLAN_CANDIDATE_VERIFICATION_REQUIRED"
    assert candidates[0].distinct_debriefs == 2


def test_single_day_noise_does_not_form_plan():
    state = DailyDebriefDigestState()
    ingest_findings(
        state,
        [
            _finding(
                "2026-09-22",
                "python-workers",
                "cloudflare-python-parity",
                "Cloudflare Python Workers GA",
                "Evaluate binding parity before runtime adoption.",
                remaining="Disposable Python Worker parity replay.",
            )
        ],
    )
    assert implementation_candidates(state) == []


def test_live_verified_repeated_lineage_can_be_ready():
    state = DailyDebriefDigestState()
    ingest_findings(
        state,
        [
            _finding(
                "2026-09-21",
                "ci-mcp-authority",
                "ci-mcp-authority",
                "CircleCI hosted MCP",
                "Split read-only and mutating tool authority.",
            ),
            _finding(
                "2026-09-22",
                "ci-live-verification",
                "ci-mcp-authority",
                "CI authority replay",
                "Require effect receipts for mutating tools.",
                validation="LIVE PASS",
            ),
        ],
    )
    candidate = implementation_candidates(state)[0]
    assert candidate.state == "READY_FOR_IMPLEMENTATION_PLAN"


def test_plan_preserves_authority_boundary():
    state = DailyDebriefDigestState()
    ingest_findings(
        state,
        [
            _finding("2026-09-21", "a", "x", "A", "Consequence A"),
            _finding("2026-09-22", "b", "x", "B", "Consequence B"),
        ],
    )
    plan = build_implementation_plan(state)
    assert plan["authority"]["research_is_evidence_not_canon"] is True
    assert plan["authority"]["automatic_runtime_activation"] is False
    assert plan["authority"]["automatic_repository_mutation"] is False


def test_distinct_debrief_count_uses_date_not_source_count():
    state = DailyDebriefDigestState()
    ingest_findings(
        state,
        [
            _finding("2026-09-21", "a", "x", "A", "Consequence A"),
            _finding("2026-09-21", "b", "x", "B", "Consequence B"),
        ],
    )
    assert implementation_candidates(state) == []
