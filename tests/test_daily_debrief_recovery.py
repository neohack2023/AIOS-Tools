from pathlib import Path

import pytest

from aios_tools.experimental.daily_debrief_adapter import (
    adapt_structured_debrief,
)
from aios_tools.experimental.daily_debrief_event_store import (
    EventStoreConcurrencyConflict,
    SqliteDailyDebriefEventStore,
    StoredEvent,
)
from aios_tools.experimental.daily_debrief_projection import (
    DailyDebriefProjectionState,
    ProjectionSequenceError,
    project_event,
    projection_digest,
    projection_envelope,
)
from aios_tools.experimental.daily_debrief_quarantine import (
    SqliteDailyDebriefQuarantineStore,
)
from aios_tools.experimental.daily_debrief_recovery import (
    RecoveryError,
    ingest_structured_debrief,
    recover_projection,
)


def _payload(
    *,
    date="2026-09-22",
    finding_id="finding.one",
    remaining=(),
    resolved=(),
    validation="SIMULATION PASS",
):
    return {
        "schema": "daily-debrief-structured/v1",
        "source_provider": "google_drive",
        "source_id": f"source-{date}-{finding_id}",
        "source_revision": f"rev-{date}-{finding_id}",
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


def _stores(tmp_path: Path):
    return (
        SqliteDailyDebriefEventStore(tmp_path / "events.sqlite"),
        SqliteDailyDebriefQuarantineStore(tmp_path / "quarantine.sqlite"),
    )


def test_exact_duplicate_delivery_is_noop(tmp_path: Path):
    events, quarantine = _stores(tmp_path)
    try:
        first = ingest_structured_debrief(
            _payload(),
            event_store=events,
            quarantine_store=quarantine,
        )
        retry = ingest_structured_debrief(
            _payload(),
            event_store=events,
            quarantine_store=quarantine,
        )

        assert first.status == "ACCEPTED"
        assert retry.status == "DUPLICATE_NOOP"
        assert events.last_sequence() == 1
    finally:
        events.close()
        quarantine.close()


def test_crash_after_append_before_projection_recovers_by_replay(tmp_path: Path):
    events, quarantine = _stores(tmp_path)
    try:
        ingest_structured_debrief(
            _payload(),
            event_store=events,
            quarantine_store=quarantine,
        )

        recovered = recover_projection(events)

        assert recovered.last_applied_sequence == 1
        assert len(recovered.processed_event_ids) == 1
    finally:
        events.close()
        quarantine.close()


def test_crash_after_projection_before_ack_does_not_double_count(tmp_path: Path):
    events, quarantine = _stores(tmp_path)
    try:
        payload = _payload(validation="LIVE PASS")
        ingest_structured_debrief(
            payload,
            event_store=events,
            quarantine_store=quarantine,
        )
        projected = recover_projection(events)
        checkpoint = projection_envelope(projected)

        retry = ingest_structured_debrief(
            payload,
            event_store=events,
            quarantine_store=quarantine,
        )
        recovered = recover_projection(
            events,
            checkpoint=checkpoint,
        )

        assert retry.status == "DUPLICATE_NOOP"
        lineage = recovered.lineages["model-lifecycle"]
        assert lineage.live_verified_count == 1
        assert recovered.last_applied_sequence == 1
    finally:
        events.close()
        quarantine.close()


def test_deleted_projection_rebuilds_to_same_digest(tmp_path: Path):
    events, quarantine = _stores(tmp_path)
    try:
        for index in range(3):
            ingest_structured_debrief(
                _payload(
                    date=f"2026-09-{20 + index}",
                    finding_id=f"finding.{index}",
                ),
                event_store=events,
                quarantine_store=quarantine,
            )

        before_delete = recover_projection(events)
        expected_digest = projection_digest(before_delete)

        rebuilt_from_nothing = recover_projection(events)

        assert projection_digest(rebuilt_from_nothing) == expected_digest
    finally:
        events.close()
        quarantine.close()


def test_out_of_order_projection_sequence_fails_closed():
    event = adapt_structured_debrief(_payload())[0]
    state = DailyDebriefProjectionState()

    with pytest.raises(
        ProjectionSequenceError,
        match="projection_sequence_mismatch",
    ):
        project_event(state, StoredEvent(sequence=2, event=event))


def test_future_schema_is_quarantined_and_not_accepted(tmp_path: Path):
    events, quarantine = _stores(tmp_path)
    try:
        payload = _payload()
        payload["schema"] = "daily-debrief-structured/v99"

        result = ingest_structured_debrief(
            payload,
            event_store=events,
            quarantine_store=quarantine,
        )

        assert result.status == "QUARANTINED"
        assert events.last_sequence() == 0
        rejected = tuple(quarantine.iter_rejections())
        assert len(rejected) == 1
        assert rejected[0].receipt["rejection_code"] == "UNKNOWN_SCHEMA"
    finally:
        events.close()
        quarantine.close()


def test_resolved_test_id_changes_only_exact_gate(tmp_path: Path):
    events, quarantine = _stores(tmp_path)
    try:
        ingest_structured_debrief(
            _payload(
                date="2026-09-21",
                finding_id="finding.a",
                remaining=("gate.a", "gate.ab"),
            ),
            event_store=events,
            quarantine_store=quarantine,
        )
        ingest_structured_debrief(
            _payload(
                date="2026-09-22",
                finding_id="finding.b",
                resolved=("gate.a",),
            ),
            event_store=events,
            quarantine_store=quarantine,
        )

        recovered = recover_projection(events)
        lineage = recovered.lineages["model-lifecycle"]

        assert lineage.remaining_test_ids == ["gate.ab"]
        assert lineage.resolved_test_ids == ["gate.a"]
    finally:
        events.close()
        quarantine.close()


def test_two_writers_same_expected_sequence_cannot_both_commit(tmp_path: Path):
    path = tmp_path / "events.sqlite"
    first = SqliteDailyDebriefEventStore(path)
    second = SqliteDailyDebriefEventStore(path)
    try:
        event_a = adapt_structured_debrief(
            _payload(finding_id="finding.a")
        )[0]
        event_b = adapt_structured_debrief(
            _payload(finding_id="finding.b")
        )[0]

        accepted = first.append(event_a, expected_sequence=0)
        assert accepted.sequence == 1

        with pytest.raises(EventStoreConcurrencyConflict):
            second.append(event_b, expected_sequence=0)

        assert first.last_sequence() == 1
        assert second.last_sequence() == 1
    finally:
        first.close()
        second.close()


def test_checkpoint_ahead_of_store_fails_closed(tmp_path: Path):
    events, quarantine = _stores(tmp_path)
    try:
        ingest_structured_debrief(
            _payload(),
            event_store=events,
            quarantine_store=quarantine,
        )
        state = recover_projection(events)
        checkpoint = projection_envelope(state)
        checkpoint["last_applied_sequence"] = 2
        checkpoint["processed_event_ids"].append(
            "ddf_" + "0" * 64
        )

        from aios_tools.canonical import canonical_sha256
        unsigned = {
            key: value
            for key, value in checkpoint.items()
            if key != "projection_digest"
        }
        checkpoint["projection_digest"] = canonical_sha256(unsigned)

        with pytest.raises(
            RecoveryError,
            match="projection_ahead_of_event_store",
        ):
            recover_projection(events, checkpoint=checkpoint)
    finally:
        events.close()
        quarantine.close()
