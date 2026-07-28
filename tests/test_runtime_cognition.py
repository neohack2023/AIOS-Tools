from __future__ import annotations

from math import nan

from aios_tools.cognition_receipt import validate_cognition_receipt
from aios_tools.runner import invoke


def _event_types(receipt: dict) -> list[str]:
    return [event["event_type"] for event in receipt["cognition_receipt"]["events"]]


def test_completed_execution_emits_aligned_cognition_receipt() -> None:
    receipt = invoke("system.health", {}, request_id="request-cognition-success")
    cognition = receipt["cognition_receipt"]

    validate_cognition_receipt(cognition)
    assert cognition["request_id"] == receipt["request_id"]
    assert cognition["scope_key"] == receipt["scope"]
    assert cognition["mode"] == receipt["mode"]
    assert cognition["status"] == receipt["status"] == "COMPLETED"
    assert cognition["started_at"] == receipt["started_at"]
    assert cognition["completed_at"] == receipt["completed_at"]
    assert "tool.invoked" in _event_types(receipt)
    assert "tool.completed" in _event_types(receipt)
    assert _event_types(receipt)[-1] == "receipt.created"


def test_blocked_execution_does_not_claim_handler_invocation() -> None:
    receipt = invoke("not.registered", {}, request_id="request-cognition-blocked")
    cognition = receipt["cognition_receipt"]

    validate_cognition_receipt(cognition)
    assert receipt["status"] == cognition["status"] == "BLOCKED"
    assert "tool.invoked" not in _event_types(receipt)
    assert "tool.blocked" in _event_types(receipt)


def test_failed_handler_execution_records_invocation_and_failure() -> None:
    receipt = invoke(
        "canonical.hash_json",
        {"value": {"not_finite": nan}},
        request_id="request-cognition-failed",
    )
    cognition = receipt["cognition_receipt"]

    validate_cognition_receipt(cognition)
    assert receipt["status"] == cognition["status"] == "FAILED"
    assert "tool.invoked" in _event_types(receipt)
    assert "tool.failed" in _event_types(receipt)


def test_runtime_trace_omits_raw_payload_and_output() -> None:
    secret_marker = "DO_NOT_COPY_RAW_PAYLOAD"
    receipt = invoke(
        "canonical.hash_json",
        {"value": {"secret": secret_marker}},
        request_id="request-cognition-redaction",
    )
    cognition_text = repr(receipt["cognition_receipt"])

    assert secret_marker not in cognition_text
    assert "output" not in cognition_text
    assert "payload" in cognition_text
