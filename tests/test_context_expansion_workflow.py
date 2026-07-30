from __future__ import annotations

import json
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator, FormatChecker

from aios_tools.context_expansion import SufficiencyAssessment
from aios_tools.context_expansion_workflow import (
    run_context_expansion_packet_workflow,
    validate_context_expansion_workflow_result,
)
from aios_tools.retrieval_trajectory import RetrievalTrajectoryBuilder


def _trajectory() -> dict:
    builder = RetrievalTrajectoryBuilder(
        scope_key="global-working-memory",
        query_ref="query:tier1-bounded-workflow",
    )
    notion = builder.consider(
        source_system="NOTION",
        source_ref="page:tier1-contract",
        authority_role="AUTHORITATIVE",
        rank=0,
        score=0.99,
    )
    drive = builder.consider(
        source_system="DRIVE",
        source_ref="file:tier1-shadow",
        authority_role="DRIVE_SHADOW",
        rank=1,
        score=0.91,
    )
    builder.decide(notion, disposition="SELECTED", reason_code="SCOPE_AND_AUTHORITY_MATCH")
    builder.decide(drive, disposition="REJECTED", reason_code="SHADOW_DUPLICATE")
    builder.compose(context_packet_id="cp_tier1_workflow_l0", packet_ids=[notion], token_count=480)
    return builder.finalize()


def _result() -> dict:
    return run_context_expansion_packet_workflow(
        request_id="request-tier1-workflow-001",
        trajectory=_trajectory(),
        assessment=SufficiencyAssessment(
            verdict="INSUFFICIENT",
            required_claims=2,
            supported_claims=1,
            evidence_refs=("claim:workflow-integration",),
        ),
        started_at="2026-07-30T19:17:00-04:00",
        completed_at="2026-07-30T19:17:01-04:00",
        current_tier="L0",
        requested_tier="L1",
        expansion_trigger="SUFFICIENCY_FAILED",
        token_budget_before=4000,
        token_budget_after=3520,
        decision_result="EXPANDED",
        decision_reason="The bounded L0 packet does not support every required workflow claim.",
        provenance=[{"source_system": "GITHUB", "source_ref": "AIOS-Tools/main"}],
    )


def test_workflow_emits_correlated_cedr_and_cognition_receipt() -> None:
    result = _result()
    record = result["context_expansion_decision"]
    receipt = result["cognition_receipt"]

    assert result["status"] == "COMPLETED"
    assert result["external_effects"] == []
    assert result["authority_transfer"] is False
    assert record["scope_key"] == receipt["scope_key"] == "global-working-memory"

    evidence = [item for event in receipt["events"] for item in event["evidence"]]
    assert any(item["evidence_id"] == record["expansion_record_id"] for item in evidence)
    assert any(
        event["event_type"] == "context.packet_composed"
        and event["evidence"][0]["evidence_id"] == record["expansion_record_id"]
        for event in receipt["events"]
    )


def test_workflow_preserves_retrieval_trajectory_order() -> None:
    trajectory = _trajectory()
    result = _result()
    receipt_types = [event["event_type"] for event in result["cognition_receipt"]["events"]]
    trajectory_types = [event["event_type"] for event in trajectory["events"]]

    start = receipt_types.index(trajectory_types[0])
    assert receipt_types[start : start + len(trajectory_types)] == trajectory_types


def test_workflow_output_is_deterministic_for_identical_inputs() -> None:
    assert _result() == _result()


def test_workflow_artifacts_match_existing_json_schemas() -> None:
    result = _result()
    contracts = Path(__file__).parents[1] / "contracts"
    cognition_schema = json.loads((contracts / "cognition-receipt.v0.1.schema.json").read_text(encoding="utf-8"))
    cedr_schema = json.loads(
        (contracts / "context-expansion-decision-record.v0.1.schema.json").read_text(encoding="utf-8")
    )

    assert list(
        Draft202012Validator(cognition_schema, format_checker=FormatChecker()).iter_errors(
            result["cognition_receipt"]
        )
    ) == []
    assert list(
        Draft202012Validator(cedr_schema, format_checker=FormatChecker()).iter_errors(
            result["context_expansion_decision"]
        )
    ) == []


def test_receipt_evidence_is_content_free_pointer_not_embedded_record() -> None:
    result = _result()
    evidence = [item for event in result["cognition_receipt"]["events"] for item in event["evidence"]]

    assert evidence
    assert all("opened_items" not in item for item in evidence)
    assert all("rejected_items" not in item for item in evidence)
    assert all("authority_sources_considered" not in item for item in evidence)
    assert all(item["authority_transfer"] is False for item in evidence)


def test_workflow_rejects_unfinalized_trajectory() -> None:
    trajectory = _trajectory()
    trajectory.pop("trajectory_id")

    with pytest.raises(ValueError, match="finalized retrieval trajectory"):
        run_context_expansion_packet_workflow(
            request_id="request-invalid",
            trajectory=trajectory,
            assessment=SufficiencyAssessment(
                verdict="INSUFFICIENT",
                required_claims=2,
                supported_claims=1,
            ),
            started_at="2026-07-30T19:17:00-04:00",
            completed_at="2026-07-30T19:17:01-04:00",
            current_tier="L0",
            requested_tier="L1",
            expansion_trigger="SUFFICIENCY_FAILED",
            token_budget_before=4000,
            token_budget_after=3520,
            decision_result="EXPANDED",
            decision_reason="Missing evidence.",
        )


def test_validator_fails_closed_if_cedr_evidence_is_removed() -> None:
    result = _result()
    for event in result["cognition_receipt"]["events"]:
        event["evidence"] = []

    with pytest.raises(ValueError, match="must reference the CEDR"):
        validate_context_expansion_workflow_result(result)
