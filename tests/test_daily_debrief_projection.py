from pathlib import Path

import pytest

from aios_tools.experimental.daily_debrief_adapter import adapt_structured_debrief
from aios_tools.experimental.daily_debrief_event_store import (
    SqliteDailyDebriefEventStore,
    StoredEvent,
)
from aios_tools.experimental.daily_debrief_projection import (
    DailyDebriefProjectionState,
    ProjectionError,
    ProjectionSequenceError,
    project_event,
    projection_digest,
    projection_envelope,
    projection_from_dict,
    projection_payload,
    rebuild_projection,
)


def _payload(date, finding_id, remaining=(), resolved=(), validation="SIMULATION PASS"):
    return {
        "schema": "daily-debrief-structured/v1",
        "source_provider": "google_drive",
        "source_id": f"source-{date}",
        "source_revision": f"rev-{date}",
        "source_digest": "a" * 64,
        "debrief_date": date,
        "scope_key": "global-working-memory",
        "findings": [
            {
                "finding_id": finding_id,
                "lineage": "model-lifecycle",
                "title": finding_id,
                "disposition": "REFINEMENT",
                "confidence": "high",
                "implementation_consequence": f"consequence-{finding_id}",
                "validation_state": validation,
                "remaining_test_ids": list(remaining),
                "resolved_test_ids": list(resolved),
            }
        ],
    }


def _event(date, finding_id, **kwargs):
    return adapt_structured_debrief(_payload(date, finding_id, **kwargs))[0]


def test_incremental_projection_equals_full_rebuild(tmp_path: Path):
    path = tmp_path / "events.sqlite"
    with SqliteDailyDebriefEventStore(path) as store:
        store.append(_event("2026-09-21", "a", remaining=("gate.a",)))
        store.append(_event("2026-09-22", "b", remaining=("gate.b",)))
        store.append(_event("2026-09-23", "c", resolved=("gate.a",), validation="LIVE PASS"))

        incremental = DailyDebriefProjectionState()
        for stored in store.iter_events():
            project_event(incremental, stored)

        rebuilt = rebuild_projection(store.iter_events())

        assert projection_payload(incremental) == projection_payload(rebuilt)
        assert projection_digest(incremental) == projection_digest(rebuilt)


def test_projection_tracks_exact_gate_resolution(tmp_path: Path):
    path = tmp_path / "events.sqlite"
    with SqliteDailyDebriefEventStore(path) as store:
        store.append(_event("2026-09-21", "a", remaining=("gate.a", "gate.b")))
        store.append(_event("2026-09-22", "b", resolved=("gate.a",)))

        state = rebuild_projection(store.iter_events())
        lineage = state.lineages["model-lifecycle"]

        assert lineage.remaining_test_ids == ["gate.b"]
        assert lineage.resolved_test_ids == ["gate.a"]


def test_resolved_gate_is_not_reopened_by_later_stale_evidence(tmp_path: Path):
    path = tmp_path / "events.sqlite"
    with SqliteDailyDebriefEventStore(path) as store:
        store.append(_event("2026-09-21", "a", remaining=("gate.a",)))
        store.append(_event("2026-09-22", "b", resolved=("gate.a",)))
        store.append(_event("2026-09-23", "c", remaining=("gate.a",)))

        state = rebuild_projection(store.iter_events())
        lineage = state.lineages["model-lifecycle"]

        assert "gate.a" not in lineage.remaining_test_ids
        assert lineage.resolved_test_ids == ["gate.a"]


def test_projection_requires_contiguous_sequence():
    state = DailyDebriefProjectionState()
    stored = StoredEvent(sequence=2, event=_event("2026-09-21", "a"))
    with pytest.raises(ProjectionSequenceError, match="expected=1:actual=2"):
        project_event(state, stored)


def test_projection_rejects_duplicate_event_identity():
    event = _event("2026-09-21", "a")
    state = DailyDebriefProjectionState()
    project_event(state, StoredEvent(sequence=1, event=event))
    with pytest.raises(ProjectionSequenceError, match="duplicate_event"):
        project_event(state, StoredEvent(sequence=2, event=event))


def test_projection_round_trip_with_digest(tmp_path: Path):
    path = tmp_path / "events.sqlite"
    with SqliteDailyDebriefEventStore(path) as store:
        store.append(_event("2026-09-21", "a"))
        state = rebuild_projection(store.iter_events())

    envelope = projection_envelope(state)
    restored = projection_from_dict(envelope)

    assert projection_payload(restored) == projection_payload(state)
    assert projection_digest(restored) == projection_digest(state)


def test_projection_tamper_detection(tmp_path: Path):
    path = tmp_path / "events.sqlite"
    with SqliteDailyDebriefEventStore(path) as store:
        store.append(_event("2026-09-21", "a"))
        state = rebuild_projection(store.iter_events())

    envelope = projection_envelope(state)
    envelope["last_applied_sequence"] = 99

    with pytest.raises(ProjectionError, match="projection_digest_mismatch"):
        projection_from_dict(envelope)


def test_validation_counts_are_rebuildable(tmp_path: Path):
    path = tmp_path / "events.sqlite"
    with SqliteDailyDebriefEventStore(path) as store:
        store.append(_event("2026-09-21", "a", validation="SIMULATION 5/5 PASS"))
        store.append(_event("2026-09-22", "b", validation="LIVE PASS"))
        state = rebuild_projection(store.iter_events())

    lineage = state.lineages["model-lifecycle"]
    assert lineage.simulation_pass_count == 1
    assert lineage.live_verified_count == 1
