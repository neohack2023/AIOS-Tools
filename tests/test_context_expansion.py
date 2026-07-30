from __future__ import annotations

import json
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator, FormatChecker

from aios_tools.context_expansion import (
    SufficiencyAssessment,
    build_context_expansion_decision,
    validate_context_expansion_decision,
    validate_sufficiency_assessment,
)
from aios_tools.retrieval_trajectory import RetrievalTrajectoryBuilder


def _trajectory() -> dict:
    builder = RetrievalTrajectoryBuilder(
        scope_key="global-working-memory",
        query_ref="query:runtime-context-expansion",
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
    builder.compose(context_packet_id="cp_tier1_l0", packet_ids=[notion], token_count=480)
    return builder.finalize()


def _record() -> dict:
    return build_context_expansion_decision(
        trajectory=_trajectory(),
        assessment=SufficiencyAssessment(
            verdict="INSUFFICIENT",
            required_claims=2,
            supported_claims=1,
            evidence_refs=("claim:context-expansion-contract",),
        ),
        created_at="2026-07-30T18:00:00-04:00",
        current_tier="L0",
        requested_tier="L1",
        expansion_trigger="SUFFICIENCY_FAILED",
        token_budget_before=4000,
        token_budget_after=3520,
        decision_result="EXPANDED",
        decision_reason="One required implementation claim remains unsupported at L0.",
    )


def test_builds_deterministic_record_from_retrieval_trajectory() -> None:
    first = _record()
    second = _record()

    assert first == second
    assert first["scope_key"] == "global-working-memory"
    assert first["packet_id"] == "cp_tier1_l0"
    assert first["sufficiency_before"] == "INSUFFICIENT"
    assert first["decision_result"] == "EXPANDED"
    assert first["opened_items"][0]["source_pointer"]["authority_role"] == "SOURCE_AUTHORITY"
    assert first["rejected_items"][0]["source_pointer"]["authority_role"] == "A1_READ"
    assert first["retrieval_path_pointer"]["trajectory_id"].startswith("rt_")
    assert first["retrieval_path_pointer"]["sufficiency_assessment_id"].startswith("sa_")
    assert first["expansion_record_id"].startswith("cedr_")


def test_record_matches_draft_2020_12_contract() -> None:
    schema_path = Path(__file__).parents[1] / "contracts" / "context-expansion-decision-record.v0.1.schema.json"
    schema = json.loads(schema_path.read_text(encoding="utf-8"))
    errors = list(Draft202012Validator(schema, format_checker=FormatChecker()).iter_errors(_record()))
    assert errors == []


def test_sufficiency_is_set_level_and_fail_closed() -> None:
    validate_sufficiency_assessment(
        SufficiencyAssessment(
            verdict="SUFFICIENT",
            required_claims=3,
            supported_claims=3,
            evidence_refs=("claim:1", "claim:2", "claim:3"),
        ).to_dict()
    )

    with pytest.raises(ValueError, match="complete support"):
        SufficiencyAssessment(
            verdict="SUFFICIENT",
            required_claims=3,
            supported_claims=2,
        ).to_dict()

    with pytest.raises(ValueError, match="authority blockage"):
        SufficiencyAssessment(
            verdict="BLOCKED",
            required_claims=2,
            supported_claims=1,
        ).to_dict()


def test_sufficiency_failed_trigger_rejects_sufficient_packet() -> None:
    record = _record()
    record["sufficiency_before"] = "SUFFICIENT"
    with pytest.raises(ValueError, match="CEDR_MISSING_SUFFICIENCY"):
        validate_context_expansion_decision(record)


def test_budget_increase_requires_approval_pointer() -> None:
    record = _record()
    record["token_budget_after"] = 5000
    with pytest.raises(ValueError, match="CEDR_UNAPPROVED_BUDGET_INCREASE"):
        validate_context_expansion_decision(record)

    record["budget_approval_pointer"] = {"policy_ref": "approval:budget-1"}
    validate_context_expansion_decision(record)


def test_tier_regression_requires_compaction_reset() -> None:
    record = _record()
    record["current_tier"] = "L2"
    record["requested_tier"] = "L1"
    with pytest.raises(ValueError, match="CEDR_ILLEGAL_TIER_TRANSITION"):
        validate_context_expansion_decision(record)

    record["expansion_trigger"] = "COMPACTION_RESET"
    record["decision_result"] = "DENIED"
    validate_context_expansion_decision(record)


def test_opened_rejected_and_omitted_items_require_reasons() -> None:
    record = _record()
    record["omitted_items"] = [
        {
            "source_pointer": {
                "source_system": "WEB",
                "source_object_id": "paper:irrelevant",
                "source_url": None,
                "authority_role": "EVIDENCE_ONLY",
                "coverage_state": "RESOLVED",
            },
            "reason": "",
        }
    ]
    with pytest.raises(ValueError, match="require reasons"):
        validate_context_expansion_decision(record)
