from pathlib import Path

import pytest

from aios_tools.experimental.daily_debrief_adapter import adapt_structured_debrief
from aios_tools.experimental.daily_debrief_event_store import (
    EventStoreConcurrencyConflict,
    EventStoreCorruption,
    SqliteDailyDebriefEventStore,
)


def _payload(finding_id="model-lifecycle.grok-4-7"):
    return {
        "schema": "daily-debrief-structured/v1",
        "source_provider": "google_drive",
        "source_id": "1nZ140nmwSUpJHDc61yI4ekKJ-dTLU40UXPodWHOZC8k",
        "source_revision": "2026-09-22T12:14:56.458Z",
        "source_digest": "a" * 64,
        "debrief_date": "2026-09-22",
        "scope_key": "global-working-memory",
        "findings": [
            {
                "finding_id": finding_id,
                "lineage": "model-lifecycle",
                "title": "Grok 4.7 in GitHub Copilot",
                "disposition": "REFINEMENT",
                "confidence": "high",
                "implementation_consequence": "Benchmark lifecycle behavior.",
                "validation_state": "RESEARCH_RETAINED",
                "remaining_test_ids": ["model-lifecycle.live-benchmark"],
                "resolved_test_ids": [],
            }
        ],
    }


def _event(finding_id="model-lifecycle.grok-4-7"):
    return adapt_structured_debrief(_payload(finding_id))[0]


def test_append_assigns_monotonic_sequence(tmp_path: Path):
    path = tmp_path / "events.sqlite"
    with SqliteDailyDebriefEventStore(path) as store:
        first = store.append(_event("finding.one"), expected_sequence=0)
        second = store.append(_event("finding.two"), expected_sequence=1)

        assert first.status == "APPENDED"
        assert first.sequence == 1
        assert second.sequence == 2
        assert store.last_sequence() == 2


def test_exact_duplicate_is_noop_even_with_stale_expected_sequence(tmp_path: Path):
    path = tmp_path / "events.sqlite"
    event = _event()

    with SqliteDailyDebriefEventStore(path) as store:
        first = store.append(event, expected_sequence=0)
        retry = store.append(event, expected_sequence=0)

        assert retry.status == "DUPLICATE_NOOP"
        assert retry.sequence == first.sequence
        assert store.last_sequence() == 1
        assert len(tuple(store.iter_events())) == 1


def test_expected_sequence_conflict_does_not_mutate_store(tmp_path: Path):
    path = tmp_path / "events.sqlite"

    with SqliteDailyDebriefEventStore(path) as store:
        store.append(_event("finding.one"), expected_sequence=0)

        with pytest.raises(
            EventStoreConcurrencyConflict,
            match="expected_sequence_mismatch",
        ):
            store.append(_event("finding.two"), expected_sequence=0)

        assert store.last_sequence() == 1
        assert not store.contains(_event("finding.two")["event_id"])


def test_two_writers_cannot_commit_same_expected_sequence(tmp_path: Path):
    path = tmp_path / "events.sqlite"

    with SqliteDailyDebriefEventStore(path) as first, \
         SqliteDailyDebriefEventStore(path) as second:
        accepted = first.append(_event("finding.one"), expected_sequence=0)
        assert accepted.sequence == 1

        with pytest.raises(EventStoreConcurrencyConflict):
            second.append(_event("finding.two"), expected_sequence=0)

        assert second.last_sequence() == 1


def test_events_survive_store_restart(tmp_path: Path):
    path = tmp_path / "events.sqlite"
    event = _event()

    with SqliteDailyDebriefEventStore(path) as store:
        stored = store.append(event)
        assert stored.sequence == 1

    with SqliteDailyDebriefEventStore(path) as reopened:
        events = tuple(reopened.iter_events())
        assert reopened.contains(event["event_id"])
        assert reopened.last_sequence() == 1
        assert events[0].event == event


def test_iter_events_resumes_after_sequence(tmp_path: Path):
    path = tmp_path / "events.sqlite"

    with SqliteDailyDebriefEventStore(path) as store:
        store.append(_event("finding.one"))
        store.append(_event("finding.two"))
        store.append(_event("finding.three"))

        resumed = tuple(store.iter_events(after_sequence=1))
        assert [stored.sequence for stored in resumed] == [2, 3]


def test_invalid_event_is_rejected_before_storage_mutation(tmp_path: Path):
    path = tmp_path / "events.sqlite"
    event = _event()
    event["implementation_consequence"] = "tampered"

    with SqliteDailyDebriefEventStore(path) as store:
        with pytest.raises(ValueError, match="event_digest_mismatch"):
            store.append(event)
        assert store.last_sequence() == 0


def test_direct_payload_corruption_is_detected_on_read(tmp_path: Path):
    path = tmp_path / "events.sqlite"
    event = _event()

    with SqliteDailyDebriefEventStore(path) as store:
        store.append(event)
        store._conn.execute(
            "UPDATE daily_debrief_events SET event_json = ? WHERE sequence = 1",
            ('{"bad":true}',),
        )

        with pytest.raises(EventStoreCorruption, match="stored_event_invalid"):
            tuple(store.iter_events())


def test_negative_sequence_inputs_fail_closed(tmp_path: Path):
    path = tmp_path / "events.sqlite"
    with SqliteDailyDebriefEventStore(path) as store:
        with pytest.raises(ValueError, match="expected_sequence"):
            store.append(_event(), expected_sequence=-1)
        with pytest.raises(ValueError, match="after_sequence"):
            tuple(store.iter_events(after_sequence=-1))
