from __future__ import annotations

import pytest

from aios_tools.retrieval_trajectory import RetrievalTrajectoryBuilder, validate_retrieval_trajectory


def _builder() -> RetrievalTrajectoryBuilder:
    return RetrievalTrajectoryBuilder(scope_key="global-working-memory", query_ref="query:test")


def test_builds_deterministic_metadata_only_trajectory() -> None:
    builder = _builder()
    notion = builder.consider(source_system="notion", source_ref="page:authority", authority_role="AUTHORITATIVE", rank=0, score=0.98)
    drive = builder.consider(source_system="google_drive", source_ref="file:shadow", authority_role="DRIVE_SHADOW", rank=1, score=0.76)
    builder.decide(notion, disposition="SELECTED", reason_code="AUTHORITY_MATCH")
    builder.decide(drive, disposition="REJECTED", reason_code="SHADOW_DUPLICATE")
    builder.compose(context_packet_id="context:test", packet_ids=[notion], token_count=240)

    trajectory = builder.finalize()
    validate_retrieval_trajectory(trajectory)

    assert trajectory["trajectory_id"].startswith("rt_")
    assert trajectory["context_packet"]["packet_ids"] == [notion]
    assert [event["event_type"] for event in trajectory["events"]] == [
        "retrieval.packet_considered",
        "retrieval.packet_selected",
        "retrieval.packet_considered",
        "retrieval.packet_rejected",
        "context.packet_composed",
    ]
    assert "content" not in repr(trajectory).lower()
    assert trajectory["external_effects"] == []
    assert trajectory["authority_transfer"] is False


def test_packet_decision_requires_prior_consideration() -> None:
    with pytest.raises(ValueError, match="prior consideration"):
        _builder().decide("rp_missing", disposition="SELECTED", reason_code="MATCH")


def test_packet_cannot_receive_two_terminal_dispositions() -> None:
    builder = _builder()
    packet = builder.consider(source_system="notion", source_ref="page:1", authority_role="AUTHORITATIVE", rank=0)
    builder.decide(packet, disposition="SELECTED", reason_code="MATCH")
    with pytest.raises(ValueError, match="already has"):
        builder.decide(packet, disposition="REJECTED", reason_code="LATE_REJECTION")


def test_rejected_packet_cannot_enter_context() -> None:
    builder = _builder()
    packet = builder.consider(source_system="google_drive", source_ref="file:1", authority_role="DRIVE_SHADOW", rank=0)
    builder.decide(packet, disposition="REJECTED", reason_code="NOT_AUTHORITY")
    with pytest.raises(ValueError, match="only selected"):
        builder.compose(context_packet_id="context:test", packet_ids=[packet], token_count=10)


def test_selected_packets_require_exact_context_membership() -> None:
    builder = _builder()
    first = builder.consider(source_system="notion", source_ref="page:1", authority_role="AUTHORITATIVE", rank=0)
    second = builder.consider(source_system="github", source_ref="blob:2", authority_role="IMPLEMENTATION", rank=1)
    builder.decide(first, disposition="SELECTED", reason_code="ARCHITECTURE_AUTHORITY")
    builder.decide(second, disposition="SELECTED", reason_code="IMPLEMENTATION_EVIDENCE")
    builder.compose(context_packet_id="context:test", packet_ids=[first], token_count=10)
    with pytest.raises(ValueError, match="exactly the selected"):
        builder.finalize()


def test_validator_rejects_content_bearing_candidate() -> None:
    trajectory = {
        "trajectory_version": "0.1",
        "scope_key": "global-working-memory",
        "query_ref": "query:test",
        "candidates": [{
            "packet_id": "rp_invalid",
            "source_system": "notion",
            "source_ref": "page:1",
            "authority_role": "AUTHORITATIVE",
            "rank": 0,
            "score": 1.0,
            "disposition": "REJECTED",
            "reason_code": "TEST",
            "content": "forbidden",
        }],
        "context_packet": None,
        "events": [],
        "external_effects": [],
        "authority_transfer": False,
    }
    with pytest.raises(ValueError, match="forbidden content"):
        validate_retrieval_trajectory(trajectory)
