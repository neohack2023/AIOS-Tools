from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Iterable

from aios_tools.experimental.daily_debrief_event_store import DailyDebriefEventStore
from aios_tools.experimental.daily_debrief_projection import (
    DailyDebriefProjectionState,
    projection_digest,
    rebuild_projection,
)
from aios_tools.experimental.daily_debrief_quarantine import DailyDebriefQuarantineStore
from aios_tools.experimental.daily_debrief_recovery import (
    ingest_structured_debrief,
    recover_projection,
)


EVALUATION_SCHEMA = "daily-debrief-seven-day-evaluation/v1"


@dataclass(frozen=True)
class FrozenCandidatePolicy:
    min_distinct_debriefs: int = 2
    min_evidence: int = 2


def candidate_snapshot(
    state: DailyDebriefProjectionState,
    policy: FrozenCandidatePolicy = FrozenCandidatePolicy(),
) -> list[dict[str, Any]]:
    candidates: list[dict[str, Any]] = []
    for lineage in sorted(state.lineages.values(), key=lambda item: item.lineage):
        evidence_count = len(lineage.event_ids)
        distinct_debriefs = len(
            {source_id.split("::", 1)[0] for source_id in lineage.source_ids}
        )
        if (
            evidence_count < policy.min_evidence
            or distinct_debriefs < policy.min_distinct_debriefs
        ):
            continue

        if lineage.live_verified_count > 0 and not lineage.remaining_test_ids:
            candidate_state = "READY_FOR_IMPLEMENTATION_PLAN"
        elif lineage.remaining_test_ids:
            candidate_state = "PLAN_CANDIDATE_VERIFICATION_REQUIRED"
        else:
            candidate_state = "PLAN_CANDIDATE"

        candidates.append(
            {
                "lineage": lineage.lineage,
                "state": candidate_state,
                "evidence_count": evidence_count,
                "distinct_debriefs": distinct_debriefs,
                "remaining_test_ids": list(lineage.remaining_test_ids),
                "live_verified_count": lineage.live_verified_count,
            }
        )
    return candidates


def evaluate_seven_day_replay(
    entries: Iterable[dict[str, Any]],
    *,
    event_store: DailyDebriefEventStore,
    quarantine_store: DailyDebriefQuarantineStore,
    policy: FrozenCandidatePolicy = FrozenCandidatePolicy(),
) -> dict[str, Any]:
    entries = list(entries)
    if len(entries) != 7:
        raise ValueError("evaluation_requires_exactly_seven_debriefs")

    days: list[dict[str, Any]] = []
    accepted_total = 0
    duplicate_total = 0
    quarantine_total = 0

    for entry in entries:
        payload = entry["payload"]
        expected = entry["expected"]
        result = ingest_structured_debrief(
            payload,
            event_store=event_store,
            quarantine_store=quarantine_store,
        )

        accepted = sum(
            1 for item in result.appended if item.status == "APPENDED"
        )
        duplicates = sum(
            1 for item in result.appended if item.status == "DUPLICATE_NOOP"
        )
        quarantined = 1 if result.status == "QUARANTINED" else 0
        accepted_total += accepted
        duplicate_total += duplicates
        quarantine_total += quarantined

        state = recover_projection(event_store)
        candidates = candidate_snapshot(state, policy)
        automatic_ready = any(
            item["state"] == "READY_FOR_IMPLEMENTATION_PLAN"
            for item in candidates
        )

        days.append(
            {
                "debrief_date": payload["debrief_date"],
                "source_id": payload["source_id"],
                "accepted_events": accepted,
                "duplicate_noops": duplicates,
                "quarantined": quarantined,
                "projection_digest": projection_digest(state),
                "candidate_count": len(candidates),
                "candidates": candidates,
                "expected_automatic_ready": expected["automatic_ready"],
                "automatic_ready": automatic_ready,
                "authority_decision_match": (
                    automatic_ready == expected["automatic_ready"]
                ),
                "human_repo_action": expected["repo_action"],
            }
        )

    incremental = recover_projection(event_store)
    rebuilt = rebuild_projection(event_store.iter_events())

    return {
        "schema": EVALUATION_SCHEMA,
        "policy": {
            "min_distinct_debriefs": policy.min_distinct_debriefs,
            "min_evidence": policy.min_evidence,
            "ready_requires_live_verified": True,
            "ready_requires_no_remaining_tests": True,
            "frozen_before_evaluation": True,
        },
        "days": days,
        "accepted_events": accepted_total,
        "duplicate_noops": duplicate_total,
        "quarantined": quarantine_total,
        "authority_decision_matches": sum(
            1 for day in days if day["authority_decision_match"]
        ),
        "incremental_digest": projection_digest(incremental),
        "rebuild_digest": projection_digest(rebuilt),
        "rebuild_match": (
            projection_digest(incremental) == projection_digest(rebuilt)
        ),
    }
