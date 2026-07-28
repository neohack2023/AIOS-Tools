from copy import deepcopy

import pytest

from aios_tools.cognition_receipt import CognitionReceiptBuilder, validate_cognition_receipt


def build_valid_receipt():
    builder = CognitionReceiptBuilder(
        trace_id="trace-1",
        request_id="request-1",
        scope_key="global-working-memory",
        mode="READ_ONLY",
        started_at="2026-07-27T22:00:00Z",
    )
    builder.append("intent.received", "2026-07-27T22:00:00Z", "assistant", {"intent_id": "intent-1"})
    builder.append("scope.candidate_considered", "2026-07-27T22:00:01Z", "scope-router", {"scope_key": "global-working-memory"})
    builder.append("scope.resolved", "2026-07-27T22:00:02Z", "scope-router", {"scope_key": "global-working-memory"})
    builder.append("authority.candidate_considered", "2026-07-27T22:00:03Z", "authority-router", {"authority_id": "notion"})
    builder.append("authority.selected", "2026-07-27T22:00:04Z", "authority-router", {"authority_id": "notion"})
    builder.append("retrieval.packet_considered", "2026-07-27T22:00:05Z", "retriever", {"packet_id": "packet-1"})
    builder.append("retrieval.packet_selected", "2026-07-27T22:00:06Z", "retriever", {"packet_id": "packet-1"})
    builder.append("context.packet_composed", "2026-07-27T22:00:07Z", "composer", {"context_packet_id": "context-1", "packet_ids": ["packet-1"]})
    builder.append("answer.generated", "2026-07-27T22:00:08Z", "assistant", {"context_packet_id": "context-1", "answer_ref": "answer-1"})
    return builder.finalize(completed_at="2026-07-27T22:00:09Z", status="COMPLETED")


def test_valid_receipt_is_deterministic():
    first = build_valid_receipt()
    second = build_valid_receipt()
    assert first == second
    assert first["receipt_id"].startswith("cr_")
    assert all(event["event_id"].startswith("ce_") for event in first["events"])


def test_rejects_non_contiguous_sequence():
    receipt = build_valid_receipt()
    receipt.pop("receipt_id")
    receipt["events"][2]["sequence"] = 9
    with pytest.raises(ValueError, match="contiguous"):
        validate_cognition_receipt(receipt)


def test_rejects_unconsidered_packet_selection():
    receipt = build_valid_receipt()
    receipt.pop("receipt_id")
    selected = next(event for event in receipt["events"] if event["event_type"] == "retrieval.packet_selected")
    selected["payload"]["packet_id"] = "packet-2"
    from aios_tools.cognition_receipt import _event_id
    selected["event_id"] = _event_id(selected)
    with pytest.raises(ValueError, match="prior consideration"):
        validate_cognition_receipt(receipt)


def test_rejects_authority_transfer_and_external_effects():
    receipt = build_valid_receipt()
    receipt.pop("receipt_id")
    receipt["authority_transfer"] = True
    with pytest.raises(ValueError, match="authority transfer"):
        validate_cognition_receipt(receipt)

    receipt = build_valid_receipt()
    receipt.pop("receipt_id")
    receipt["external_effects"] = [{"type": "write"}]
    with pytest.raises(ValueError, match="read-only"):
        validate_cognition_receipt(receipt)


def test_rejects_answer_without_matching_composed_packet():
    receipt = build_valid_receipt()
    receipt.pop("receipt_id")
    answer = next(event for event in receipt["events"] if event["event_type"] == "answer.generated")
    answer["payload"]["context_packet_id"] = "missing"
    from aios_tools.cognition_receipt import _event_id
    answer["event_id"] = _event_id(answer)
    with pytest.raises(ValueError, match="composed context"):
        validate_cognition_receipt(receipt)
