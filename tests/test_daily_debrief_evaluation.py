import json
from pathlib import Path

from aios_tools.experimental.daily_debrief_evaluation import (
    FrozenCandidatePolicy,
    evaluate_seven_day_replay,
)
from aios_tools.experimental.daily_debrief_event_store import (
    SqliteDailyDebriefEventStore,
)
from aios_tools.experimental.daily_debrief_quarantine import (
    SqliteDailyDebriefQuarantineStore,
)


FIXTURE = (
    Path(__file__).parent
    / "fixtures"
    / "daily_debrief_replay_2026-09-16_22.json"
)


def _load():
    return json.loads(FIXTURE.read_text(encoding="utf-8"))


def test_fixture_freezes_threshold_before_evaluation():
    fixture = _load()
    policy = fixture["threshold_policy"]

    assert policy["frozen_before_evaluation"] is True
    assert policy["min_distinct_debriefs"] == 2
    assert policy["min_evidence"] == 2
    assert len(fixture["entries"]) == 7


def test_seven_day_replay_matches_human_authority_decisions(tmp_path: Path):
    fixture = _load()
    with SqliteDailyDebriefEventStore(
        tmp_path / "events.sqlite"
    ) as events, SqliteDailyDebriefQuarantineStore(
        tmp_path / "quarantine.sqlite"
    ) as quarantine:
        report = evaluate_seven_day_replay(
            fixture["entries"],
            event_store=events,
            quarantine_store=quarantine,
            policy=FrozenCandidatePolicy(),
        )

    assert report["accepted_events"] == 34
    assert report["duplicate_noops"] == 0
    assert report["quarantined"] == 0
    assert report["authority_decision_matches"] == 7
    assert report["rebuild_match"] is True


def test_repeated_lineages_stop_at_verification_required(tmp_path: Path):
    fixture = _load()
    with SqliteDailyDebriefEventStore(
        tmp_path / "events.sqlite"
    ) as events, SqliteDailyDebriefQuarantineStore(
        tmp_path / "quarantine.sqlite"
    ) as quarantine:
        report = evaluate_seven_day_replay(
            fixture["entries"],
            event_store=events,
            quarantine_store=quarantine,
        )

    final = {
        item["lineage"]: item
        for item in report["days"][-1]["candidates"]
    }

    for lineage in (
        "coding-agent-harness",
        "agent-observability",
        "agent-skill-install-lifecycle",
        "agent-runtime-migration",
        "permission-policy",
        "mcp-tool-policy",
        "model-lifecycle",
    ):
        assert final[lineage]["state"] == (
            "PLAN_CANDIDATE_VERIFICATION_REQUIRED"
        )
        assert final[lineage]["live_verified_count"] == 0
        assert final[lineage]["remaining_test_ids"]


def test_bounded_human_implementation_is_not_misread_as_auto_promotion(tmp_path: Path):
    fixture = _load()
    with SqliteDailyDebriefEventStore(
        tmp_path / "events.sqlite"
    ) as events, SqliteDailyDebriefQuarantineStore(
        tmp_path / "quarantine.sqlite"
    ) as quarantine:
        report = evaluate_seven_day_replay(
            fixture["entries"],
            event_store=events,
            quarantine_store=quarantine,
        )

    day = next(
        item
        for item in report["days"]
        if item["debrief_date"] == "2026-09-21"
    )
    assert day["human_repo_action"] == "BOUNDED_IMPLEMENTATION_ADDENDUM"
    assert day["automatic_ready"] is False
    assert day["authority_decision_match"] is True


def test_nonconsecutive_window_fails_closed(tmp_path: Path):
    fixture = _load()
    entries = fixture["entries"]
    entries[3]["payload"]["debrief_date"] = "2026-09-25"

    with SqliteDailyDebriefEventStore(
        tmp_path / "events.sqlite"
    ) as events, SqliteDailyDebriefQuarantineStore(
        tmp_path / "quarantine.sqlite"
    ) as quarantine:
        try:
            evaluate_seven_day_replay(
                entries,
                event_store=events,
                quarantine_store=quarantine,
            )
        except ValueError as exc:
            assert str(exc) == "evaluation_window_not_consecutive"
        else:
            raise AssertionError("expected nonconsecutive window rejection")


def test_candidate_transition_counts_match_frozen_replay(tmp_path: Path):
    fixture = _load()
    with SqliteDailyDebriefEventStore(
        tmp_path / "events.sqlite"
    ) as events, SqliteDailyDebriefQuarantineStore(
        tmp_path / "quarantine.sqlite"
    ) as quarantine:
        report = evaluate_seven_day_replay(
            fixture["entries"],
            event_store=events,
            quarantine_store=quarantine,
        )

    assert [day["candidate_count"] for day in report["days"]] == [
        0, 1, 2, 4, 6, 6, 7
    ]
    assert report["days"][-1]["lineage_count"] == 23
    assert [
        change["lineage"]
        for change in report["days"][-1]["candidate_state_changes"]
    ] == ["model-lifecycle"]
