from __future__ import annotations

import json
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator, FormatChecker

from aios_tools.context_expansion import SufficiencyAssessment
from aios_tools.context_expansion_workflow import run_context_expansion_packet_workflow
from aios_tools.observatory_projection import (
    build_context_expansion_observatory_projection,
    validate_observatory_projection,
)
from aios_tools.retrieval_trajectory import RetrievalTrajectoryBuilder


def _trajectory() -> dict:
    builder = RetrievalTrajectoryBuilder(
        scope_key="global-working-memory",
        query_ref="query:tier1-observatory-projection",
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
    builder.compose(context_packet_id="cp_tier1_observatory_l0", packet_ids=[notion], token_count=480)
    return builder.finalize()


def _workflow_result() -> dict:
    return run_context_expansion_packet_workflow(
        request_id="request-tier1-observatory-001",
        trajectory=_trajectory(),
        assessment=SufficiencyAssessment(
            verdict="INSUFFICIENT",
            required_claims=2,
            supported_claims=1,
            evidence_refs=("claim:observatory-projection",),
        ),
        started_at="2026-07-30T19:33:00-04:00",
        completed_at="2026-07-30T19:33:01-04:00",
        current_tier="L0",
        requested_tier="L1",
        expansion_trigger="SUFFICIENCY_FAILED",
        token_budget_before=4000,
        token_budget_after=3520,
        decision_result="EXPANDED",
        decision_reason="The L0 packet does not support every required claim.",
        provenance=[{"source_system": "GITHUB", "source_ref": "AIOS-Tools/main"}],
    )


def _projection() -> dict:
    return build_context_expansion_observatory_projection(_workflow_result())


def _all_keys(value: object) -> set[str]:
    keys: set[str] = set()
    if isinstance(value, dict):
        keys.update(value)
        for item in value.values():
            keys.update(_all_keys(item))
    elif isinstance(value, list):
        for item in value:
            keys.update(_all_keys(item))
    return keys


def test_projection_exposes_only_bounded_observatory_metadata() -> None:
    projection = _projection()

    assert projection["projection_kind"] == "CONTEXT_EXPANSION_OBSERVATORY"
    assert projection["workflow"]["status"] == "COMPLETED"
    assert projection["workflow"]["mode"] == "READ_ONLY"
    assert projection["context_expansion"] == {
        "current_tier": "L0",
        "requested_tier": "L1",
        "tier_movement": "L0->L1",
        "sufficiency_verdict": "INSUFFICIENT",
        "expansion_trigger": "SUFFICIENCY_FAILED",
        "decision_result": "EXPANDED",
        "budget_state": "WITHIN_BUDGET",
        "lifecycle_state": "CANDIDATE",
    }
    assert projection["external_effects"] == []
    assert projection["authority_transfer"] is False
    assert all(value is False for value in projection["privacy"].values())


def test_projection_preserves_identity_separation_without_inventing_execution_id() -> None:
    projection = _projection()
    identities = projection["identities"]

    assert identities["request_id"] == "request-tier1-observatory-001"
    assert identities["trace_id"] == "trace-request-tier1-observatory-001"
    assert identities["receipt_id"].startswith("cr_")
    assert identities["trajectory_id"].startswith("rt_")
    assert identities["context_packet_id"] == "cp_tier1_observatory_l0"
    assert identities["expansion_record_id"].startswith("cedr_")
    assert identities["execution_id"] is None


def test_projection_preserves_explicit_execution_id_when_available() -> None:
    result = _workflow_result()
    result["execution_id"] = "execution-tier1-observatory-001"

    projection = build_context_expansion_observatory_projection(result)

    assert projection["identities"]["execution_id"] == "execution-tier1-observatory-001"
    assert projection["identities"]["execution_id"] != projection["identities"]["trace_id"]


def test_projection_deduplicates_content_free_cedr_evidence_links() -> None:
    projection = _projection()

    assert len(projection["evidence_links"]) == 1
    link = projection["evidence_links"][0]
    assert link["evidence_id"] == projection["identities"]["expansion_record_id"]
    assert link["authority_transfer"] is False
    assert link["referenced_by_event_types"] == [
        "context.packet_composed",
        "outcome.observed",
        "receipt.created",
    ]


def test_projection_omits_raw_receipt_cedr_events_and_source_content() -> None:
    projection = _projection()
    keys = _all_keys(projection)

    assert "events" not in keys
    assert "payload" not in keys
    assert "context_expansion_decision" not in keys
    assert "cognition_receipt" not in keys
    assert "opened_items" not in keys
    assert "rejected_items" not in keys
    assert "authority_sources_considered" not in keys
    assert "decision_reason" not in keys
    assert "source_content" not in keys


def test_projection_is_deterministic_for_identical_workflow_results() -> None:
    assert _projection() == _projection()


def test_projection_matches_json_schema() -> None:
    projection = _projection()
    schema_path = (
        Path(__file__).parents[1]
        / "contracts"
        / "observatory-context-expansion-projection.v0.1.schema.json"
    )
    schema = json.loads(schema_path.read_text(encoding="utf-8"))

    errors = list(
        Draft202012Validator(schema, format_checker=FormatChecker()).iter_errors(projection)
    )
    assert errors == []


def test_validator_rejects_raw_event_payload_injection() -> None:
    projection = _projection()
    projection["events"] = [{"payload": {"source_content": "forbidden"}}]

    with pytest.raises(ValueError, match="forbidden raw fields"):
        validate_observatory_projection(projection)


def test_validator_rejects_canonical_id_drift() -> None:
    projection = _projection()
    projection["context_expansion"]["decision_result"] = "DENIED"

    with pytest.raises(ValueError, match="ID does not match canonical content"):
        validate_observatory_projection(projection)
