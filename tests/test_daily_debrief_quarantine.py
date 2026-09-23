from pathlib import Path

import pytest

from aios_tools.experimental.daily_debrief_adapter import (
    DailyDebriefAdapterError,
    adapt_structured_debrief,
)
from aios_tools.experimental.daily_debrief_event_store import (
    SqliteDailyDebriefEventStore,
)
from aios_tools.experimental.daily_debrief_quarantine import (
    QuarantineCorruption,
    QuarantineError,
    SqliteDailyDebriefQuarantineStore,
    build_rejection_receipt,
    classify_rejection,
    quarantine_rejection,
    validate_rejection_receipt,
)


def _payload():
    return {
        "schema": "daily-debrief-structured/v1",
        "source_provider": "google_drive",
        "source_id": "drive-file-1",
        "source_revision": "rev-1",
        "source_digest": "a" * 64,
        "debrief_date": "2026-09-22",
        "scope_key": "global-working-memory",
        "findings": [
            {
                "finding_id": "finding.one",
                "lineage": "model-lifecycle",
                "title": "Finding one",
                "disposition": "REFINEMENT",
                "confidence": "high",
                "implementation_consequence": "Use a lifecycle gate.",
                "validation_state": "RESEARCH_RETAINED",
                "remaining_test_ids": [],
                "resolved_test_ids": [],
            }
        ],
    }


@pytest.mark.parametrize(
    ("message", "expected"),
    [
        ("unknown_schema", "UNKNOWN_SCHEMA"),
        ("scope_unresolved", "SCOPE_UNRESOLVED"),
        ("source_identity_missing", "SOURCE_IDENTITY_MISSING"),
        ("source_revision_missing", "SOURCE_REVISION_MISSING"),
        ("event_digest_mismatch", "EVENT_DIGEST_MISMATCH"),
        ("projection_sequence_mismatch:expected=1:actual=2", "OUT_OF_ORDER_SEQUENCE"),
        ("unsupported_authority_claim:canon", "UNSUPPORTED_AUTHORITY_CLAIM"),
        ("something_else", "VALIDATION_FAILED"),
    ],
)
def test_classify_rejection(message, expected):
    assert classify_rejection(message) == expected


def test_rejection_receipt_is_bounded_metadata_only():
    payload = _payload()
    payload["secret_body"] = "this must never be persisted"
    receipt = build_rejection_receipt(
        payload,
        DailyDebriefAdapterError("unknown_schema"),
    )

    assert receipt["source_id"] == "drive-file-1"
    assert receipt["source_revision"] == "rev-1"
    assert receipt["scope_key"] == "global-working-memory"
    assert receipt["payload_digest"]
    assert "secret_body" not in receipt
    assert "findings" not in receipt
    validate_rejection_receipt(receipt)


def test_future_schema_can_be_quarantined(tmp_path: Path):
    payload = _payload()
    payload["schema"] = "daily-debrief-structured/v99"

    try:
        adapt_structured_debrief(payload)
    except DailyDebriefAdapterError as exc:
        with SqliteDailyDebriefQuarantineStore(
            tmp_path / "quarantine.sqlite"
        ) as store:
            result = quarantine_rejection(store, payload, exc)
            stored = tuple(store.iter_rejections())
    else:
        raise AssertionError("expected adapter rejection")

    assert result.status == "QUARANTINED"
    assert stored[0].receipt["rejection_code"] == "UNKNOWN_SCHEMA"
    assert stored[0].receipt["schema_observed"] == "daily-debrief-structured/v99"


def test_authority_smuggling_is_quarantined_without_raw_payload(tmp_path: Path):
    payload = _payload()
    payload["metadata"] = {
        "authority": "CANON",
        "sensitive_note": "do not persist",
    }

    try:
        adapt_structured_debrief(payload)
    except DailyDebriefAdapterError as exc:
        with SqliteDailyDebriefQuarantineStore(
            tmp_path / "quarantine.sqlite"
        ) as store:
            quarantine_rejection(store, payload, exc)
            receipt = tuple(store.iter_rejections())[0].receipt
    else:
        raise AssertionError("expected adapter rejection")

    assert receipt["rejection_code"] == "UNSUPPORTED_AUTHORITY_CLAIM"
    assert "metadata" not in receipt
    assert "sensitive_note" not in receipt


def test_duplicate_rejection_is_noop(tmp_path: Path):
    path = tmp_path / "quarantine.sqlite"
    receipt = build_rejection_receipt(_payload(), "unknown_schema")

    with SqliteDailyDebriefQuarantineStore(path) as store:
        first = store.append(receipt)
        retry = store.append(receipt)

        assert first.status == "QUARANTINED"
        assert retry.status == "DUPLICATE_NOOP"
        assert retry.sequence == first.sequence
        assert len(tuple(store.iter_rejections())) == 1


def test_quarantine_does_not_mutate_main_event_store(tmp_path: Path):
    event_path = tmp_path / "events.sqlite"
    quarantine_path = tmp_path / "quarantine.sqlite"
    payload = _payload()
    payload["schema"] = "future/v99"

    with SqliteDailyDebriefEventStore(event_path) as event_store, \
         SqliteDailyDebriefQuarantineStore(quarantine_path) as quarantine:
        with pytest.raises(DailyDebriefAdapterError) as captured:
            adapt_structured_debrief(payload)

        quarantine_rejection(
            quarantine,
            payload,
            captured.value,
        )

        assert event_store.last_sequence() == 0
        assert tuple(event_store.iter_events()) == ()
        assert len(tuple(quarantine.iter_rejections())) == 1


def test_receipt_tampering_is_detected():
    receipt = build_rejection_receipt(_payload(), "unknown_schema")
    receipt["source_id"] = "tampered"

    with pytest.raises(QuarantineError, match="rejection_digest_mismatch"):
        validate_rejection_receipt(receipt)


def test_raw_content_fields_are_rejected():
    receipt = build_rejection_receipt(_payload(), "unknown_schema")
    receipt["raw_payload"] = {"bad": True}

    with pytest.raises(
        QuarantineError,
        match="quarantine_receipt_contains_source_content",
    ):
        validate_rejection_receipt(receipt)


def test_backing_store_corruption_fails_closed(tmp_path: Path):
    path = tmp_path / "quarantine.sqlite"
    receipt = build_rejection_receipt(_payload(), "unknown_schema")

    with SqliteDailyDebriefQuarantineStore(path) as store:
        store.append(receipt)
        store._conn.execute(
            """
            UPDATE daily_debrief_quarantine
            SET receipt_json = ?
            WHERE sequence = 1
            """,
            ('{"bad":true}',),
        )

        with pytest.raises(
            QuarantineCorruption,
            match="quarantine_receipt_invalid",
        ):
            tuple(store.iter_rejections())


def test_non_json_payload_still_gets_bounded_receipt():
    receipt = build_rejection_receipt(
        {"schema": "future/v99", "bad": {object()}},
        "unknown_schema",
    )

    assert receipt["rejection_code"] == "UNKNOWN_SCHEMA"
    assert receipt["payload_digest"] is None
    validate_rejection_receipt(receipt)
