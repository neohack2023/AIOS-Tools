from __future__ import annotations

from aios_tools.browser.evidence import BrowserEvidence
from aios_tools.browser.redaction import SecretEvidenceBlackout, SecretEvidenceKind


SECRET = "synthetic-secret-never-durable"


def test_secret_entry_evidence_blackout_suppresses_sensitive_values():
    evidence = BrowserEvidence(target_origin="https://example.invalid", context_id="ctx-test")
    blackout = SecretEvidenceBlackout()

    with blackout:
        assert blackout.active is True
        assert blackout.allow_screenshot is False
        assert blackout.allow_trace_snapshot is False
        assert blackout.note_screenshot_attempt() is False
        assert blackout.note_trace_snapshot_attempt() is False
        blackout.redact_form_value(SECRET)
        blackout.redact_request_body({"password": SECRET})
        blackout.redact_sensitive_headers({"authorization": SECRET})
        blackout.capture_console(evidence, kind="log", text=SECRET)
        blackout.capture_page_error(evidence, text=SECRET)

    assert blackout.active is False
    assert evidence.console == []
    assert evidence.page_errors == []
    receipt = blackout.public_receipt()
    rendered = repr(receipt)
    assert SECRET not in rendered
    assert receipt["secret_values_recorded"] is False
    assert receipt["redaction_counts"] == {
        "screenshots": 1,
        "trace_snapshots": 1,
        "form_values": 1,
        "request_bodies": 1,
        "sensitive_headers": 1,
        "console_events": 1,
        "page_errors": 1,
    }


def test_blackout_does_not_suppress_nonsecret_console_after_user_control():
    evidence = BrowserEvidence(target_origin="https://example.invalid", context_id="ctx-test")
    blackout = SecretEvidenceBlackout()
    with blackout:
        blackout.capture_console(evidence, kind="log", text=SECRET)
    blackout.capture_console(evidence, kind="log", text="authenticated-state-confirmed")
    assert len(evidence.console) == 1
    assert SECRET not in repr(evidence.to_dict())


def test_form_values_never_become_normal_takeover_evidence_outside_blackout():
    blackout = SecretEvidenceBlackout()
    try:
        blackout.redact_form_value(SECRET)
    except RuntimeError as exc:
        assert "never enter durable browser evidence" in str(exc)
    else:
        raise AssertionError("form values outside blackout must fail closed")


def test_blackout_cannot_be_nested():
    blackout = SecretEvidenceBlackout()
    try:
        with blackout:
            blackout.__enter__()
    except RuntimeError as exc:
        assert "cannot be nested" in str(exc)
    else:
        raise AssertionError("nested secret blackout must fail closed")


def test_redaction_receipt_contains_counts_only_not_values():
    blackout = SecretEvidenceBlackout()
    with blackout:
        blackout.suppress(SecretEvidenceKind.CONSOLE_EVENT)
        blackout.suppress(SecretEvidenceKind.FORM_VALUE)
    receipt = blackout.public_receipt()
    assert set(receipt) == {"active", "redaction_counts", "secret_values_recorded"}
    assert SECRET not in repr(receipt)
