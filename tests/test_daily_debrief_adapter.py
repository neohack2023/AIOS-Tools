from copy import deepcopy

import pytest

from aios_tools.experimental.daily_debrief_adapter import (
    DailyDebriefAdapterError,
    EVENT_SCHEMA,
    adapt_structured_debrief,
    validate_finding_event,
)


def _payload():
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
                "finding_id": "model-lifecycle.grok-4-7",
                "lineage": "model-lifecycle",
                "title": "Grok 4.7 in GitHub Copilot",
                "disposition": "REFINEMENT",
                "confidence": "high",
                "implementation_consequence": (
                    "Treat newly available models as lifecycle benchmark "
                    "candidates until verification."
                ),
                "validation_state": "RESEARCH_RETAINED",
                "remaining_test_ids": [
                    "model-lifecycle.live-benchmark",
                    "model-lifecycle.frozen-prompt-replay",
                ],
                "resolved_test_ids": [],
            }
        ],
    }


def test_adapter_emits_deterministic_content_addressed_event():
    first = adapt_structured_debrief(_payload())
    second = adapt_structured_debrief(_payload())
    assert first == second
    assert len(first) == 1
    assert first[0]["schema_version"] == EVENT_SCHEMA
    assert first[0]["event_id"].startswith("ddf_")
    validate_finding_event(first[0])


def test_order_of_test_ids_does_not_change_event_identity():
    payload = _payload()
    payload["findings"][0]["remaining_test_ids"].reverse()
    reversed_event = adapt_structured_debrief(payload)[0]

    normal_event = adapt_structured_debrief(_payload())[0]
    assert reversed_event["event_id"] == normal_event["event_id"]
    assert reversed_event["remaining_test_ids"] == sorted(
        reversed_event["remaining_test_ids"]
    )


@pytest.mark.parametrize(
    ("mutation", "expected"),
    [
        (lambda p: p.update(schema="future/v99"), "unknown_schema"),
        (lambda p: p.update(scope_key=""), "scope_unresolved"),
        (lambda p: p.update(source_id=""), "source_identity_missing"),
        (lambda p: p.update(source_revision=""), "source_revision_missing"),
        (lambda p: p.update(source_digest="bad"), "source_digest_invalid"),
        (lambda p: p.update(authority="CANON"), "unsupported_authority_claim"),
    ],
)
def test_adapter_fails_closed_on_invalid_envelope(mutation, expected):
    payload = _payload()
    mutation(payload)
    with pytest.raises(DailyDebriefAdapterError, match=expected):
        adapt_structured_debrief(payload)


def test_adapter_rejects_authority_claim_inside_finding():
    payload = _payload()
    payload["findings"][0]["runtime_activation"] = True
    with pytest.raises(
        DailyDebriefAdapterError, match="unsupported_authority_claim"
    ):
        adapt_structured_debrief(payload)


def test_adapter_rejects_duplicate_finding_identity():
    payload = _payload()
    payload["findings"].append(deepcopy(payload["findings"][0]))
    with pytest.raises(DailyDebriefAdapterError, match="duplicate_finding_id"):
        adapt_structured_debrief(payload)


def test_adapter_rejects_test_id_in_remaining_and_resolved_sets():
    payload = _payload()
    payload["findings"][0]["resolved_test_ids"] = [
        "model-lifecycle.live-benchmark"
    ]
    with pytest.raises(DailyDebriefAdapterError, match="test_id_conflict"):
        adapt_structured_debrief(payload)


def test_event_validation_detects_tampering():
    event = adapt_structured_debrief(_payload())[0]
    event["implementation_consequence"] = "tampered"
    with pytest.raises(DailyDebriefAdapterError, match="event_digest_mismatch"):
        validate_finding_event(event)


def test_additive_unknown_non_authority_fields_do_not_change_event_contract():
    payload = _payload()
    payload["producer_note"] = "ignored transport metadata"
    payload["findings"][0]["research_note"] = "ignored producer detail"
    event = adapt_structured_debrief(payload)[0]

    baseline = adapt_structured_debrief(_payload())[0]
    assert event == baseline


def test_adapter_rejects_nested_authority_claim():
    payload = _payload()
    payload["metadata"] = {"routing": {"authority": "CANON"}}
    with pytest.raises(
        DailyDebriefAdapterError, match="unsupported_authority_claim"
    ):
        adapt_structured_debrief(payload)
