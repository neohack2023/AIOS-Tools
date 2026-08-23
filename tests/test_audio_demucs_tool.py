from __future__ import annotations

from aios_tools.runner import invoke


PAYLOAD = {
    "source_path": "/does/not/matter/source.wav",
    "output_dir": "/does/not/matter/output",
    "profile_path": "/does/not/matter/profile.json",
}


def test_demucs_write_requires_approval_before_handler_invocation() -> None:
    receipt = invoke(
        "audio.demucs.separate",
        PAYLOAD,
        mode="WRITE",
        scope="udio-algorithms",
        request_id="request-demucs-approval-required",
    )

    assert receipt["status"] == "APPROVAL_REQUIRED"
    assert receipt["effect_class"] == "LOCAL_DURABLE_WRITE"
    assert receipt["errors"][0]["code"] == "APPROVAL_REQUIRED"
    assert receipt["authority_transfer"] is False
    assert receipt["external_effects"] == []
    event_types = [event["event_type"] for event in receipt["cognition_receipt"]["events"]]
    assert "tool.invoked" not in event_types


def test_demucs_write_rejects_scope_mismatched_approval() -> None:
    receipt = invoke(
        "audio.demucs.separate",
        PAYLOAD,
        mode="WRITE",
        scope="udio-algorithms",
        request_id="request-demucs-scope-mismatch",
        authority_context={
            "approval": {
                "approved": True,
                "approved_by": "test-human",
                "tool": "audio.demucs.separate",
                "scope": "different-scope",
            }
        },
    )

    assert receipt["status"] == "APPROVAL_REQUIRED"
    assert receipt["effect_class"] == "LOCAL_DURABLE_WRITE"
    assert receipt["errors"][0]["code"] == "APPROVAL_SCOPE_MISMATCH"
    event_types = [event["event_type"] for event in receipt["cognition_receipt"]["events"]]
    assert "tool.invoked" not in event_types
