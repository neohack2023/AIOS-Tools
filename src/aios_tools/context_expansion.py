from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .canonical import canonical_sha256
from .retrieval_trajectory import validate_retrieval_trajectory

TIERS = {"L0": 0, "L1": 1, "L2": 2}
TRIGGERS = {
    "SUFFICIENCY_FAILED",
    "AUTHORITY_AMBIGUITY",
    "CONFLICT_DETECTED",
    "EVIDENCE_GAP",
    "USER_REQUEST",
    "BUDGET_REALLOCATION",
    "RECOVERY",
    "COMPACTION_RESET",
}
SUFFICIENCY_VERDICTS = {"SUFFICIENT", "INSUFFICIENT", "UNKNOWN", "BLOCKED"}
DECISION_RESULTS = {"EXPANDED", "DENIED", "BLOCKED", "NO_OP"}
LIFECYCLE_STATES = {"CANDIDATE", "ACTIVE", "SUPERSEDED", "REJECTED"}
SOURCE_AUTHORITY_MAP = {
    "AUTHORITATIVE": "SOURCE_AUTHORITY",
    "DRIVE_SHADOW": "A1_READ",
    "IMPLEMENTATION": "IMPLEMENTATION_TRUTH",
    "EVIDENCE": "EVIDENCE_ONLY",
    "UNRESOLVED": None,
}


def _record_id(value: dict[str, Any]) -> str:
    payload = {key: item for key, item in value.items() if key != "expansion_record_id"}
    return f"cedr_{canonical_sha256(payload)}"


@dataclass(frozen=True)
class SufficiencyAssessment:
    verdict: str
    required_claims: int
    supported_claims: int
    unresolved_conflicts: int = 0
    authority_blocked: bool = False
    evidence_unknown: bool = False
    evidence_refs: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        value = {
            "assessment_version": "0.1",
            "method": "explicit-set-level-signals",
            "verdict": self.verdict,
            "required_claims": self.required_claims,
            "supported_claims": self.supported_claims,
            "unresolved_conflicts": self.unresolved_conflicts,
            "authority_blocked": self.authority_blocked,
            "evidence_unknown": self.evidence_unknown,
            "evidence_refs": list(self.evidence_refs),
        }
        validate_sufficiency_assessment(value)
        value["assessment_id"] = f"sa_{canonical_sha256(value)}"
        return value


def validate_sufficiency_assessment(assessment: dict[str, Any]) -> None:
    verdict = assessment.get("verdict")
    required = assessment.get("required_claims")
    supported = assessment.get("supported_claims")
    conflicts = assessment.get("unresolved_conflicts")
    if verdict not in SUFFICIENCY_VERDICTS:
        raise ValueError("unsupported sufficiency verdict")
    if not isinstance(required, int) or required < 0:
        raise ValueError("required_claims must be a non-negative integer")
    if not isinstance(supported, int) or supported < 0 or supported > required:
        raise ValueError("supported_claims must be between zero and required_claims")
    if not isinstance(conflicts, int) or conflicts < 0:
        raise ValueError("unresolved_conflicts must be a non-negative integer")

    blocked = bool(assessment.get("authority_blocked")) or conflicts > 0
    unknown = bool(assessment.get("evidence_unknown")) or required == 0
    if verdict == "BLOCKED" and not blocked:
        raise ValueError("BLOCKED requires authority blockage or unresolved conflict")
    if verdict == "UNKNOWN" and not unknown:
        raise ValueError("UNKNOWN requires unknown evidence or an undefined claim set")
    if verdict == "SUFFICIENT" and (blocked or unknown or supported != required):
        raise ValueError("SUFFICIENT requires complete support with no block or unknown state")
    if verdict == "INSUFFICIENT" and (blocked or unknown or supported >= required):
        raise ValueError("INSUFFICIENT requires a known, unblocked support gap")


def _source_pointer(candidate: dict[str, Any]) -> dict[str, Any]:
    authority_role = SOURCE_AUTHORITY_MAP[candidate["authority_role"]]
    unresolved = candidate["authority_role"] == "UNRESOLVED"
    return {
        "source_system": candidate["source_system"],
        "source_object_id": candidate["source_ref"],
        "source_url": None,
        "authority_role": authority_role,
        "coverage_state": "UNRESOLVED" if unresolved else "RESOLVED",
    }


def build_context_expansion_decision(
    *,
    trajectory: dict[str, Any],
    assessment: SufficiencyAssessment | dict[str, Any],
    created_at: str,
    current_tier: str,
    requested_tier: str,
    expansion_trigger: str,
    token_budget_before: int,
    token_budget_after: int,
    decision_result: str,
    decision_reason: str,
    lifecycle_state: str = "CANDIDATE",
    budget_approval_pointer: dict[str, Any] | None = None,
    omitted_items: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    validate_retrieval_trajectory(trajectory)
    assessment_value = assessment.to_dict() if isinstance(assessment, SufficiencyAssessment) else dict(assessment)
    validate_sufficiency_assessment(assessment_value)
    if not assessment_value.get("assessment_id"):
        assessment_payload = {key: value for key, value in assessment_value.items() if key != "assessment_id"}
        assessment_value["assessment_id"] = f"sa_{canonical_sha256(assessment_payload)}"

    context_packet = trajectory.get("context_packet")
    if context_packet is None:
        raise ValueError("context expansion requires a composed context packet")

    candidates = trajectory["candidates"]
    opened_items = [
        {"source_pointer": _source_pointer(item), "reason": item["reason_code"]}
        for item in candidates
        if item["disposition"] == "SELECTED"
    ]
    rejected_items = [
        {"source_pointer": _source_pointer(item), "reason": item["reason_code"]}
        for item in candidates
        if item["disposition"] == "REJECTED"
    ]
    authority_sources = []
    seen_sources: set[tuple[str, str]] = set()
    for item in candidates:
        key = (item["source_system"], item["source_ref"])
        if key not in seen_sources:
            authority_sources.append(_source_pointer(item))
            seen_sources.add(key)

    record = {
        "schema_version": "0.1",
        "packet_id": context_packet["context_packet_id"],
        "scope_key": trajectory["scope_key"],
        "created_at": created_at,
        "current_tier": current_tier,
        "requested_tier": requested_tier,
        "expansion_trigger": expansion_trigger,
        "sufficiency_before": assessment_value["verdict"],
        "authority_sources_considered": authority_sources,
        "opened_items": opened_items,
        "rejected_items": rejected_items,
        "omitted_items": list(omitted_items or []),
        "token_budget_before": token_budget_before,
        "token_budget_after": token_budget_after,
        "budget_state": "APPROVED_INCREASE" if token_budget_after > token_budget_before else "WITHIN_BUDGET",
        "retrieval_path_pointer": {
            "trajectory_id": trajectory.get("trajectory_id"),
            "query_ref": trajectory["query_ref"],
            "sufficiency_assessment_id": assessment_value.get("assessment_id"),
        },
        "decision_result": decision_result,
        "decision_reason": decision_reason,
        "lifecycle_state": lifecycle_state,
    }
    if budget_approval_pointer is not None:
        record["budget_approval_pointer"] = budget_approval_pointer
    validate_context_expansion_decision(record)
    record["expansion_record_id"] = _record_id(record)
    return record


def validate_context_expansion_decision(record: dict[str, Any]) -> None:
    required = {
        "schema_version",
        "packet_id",
        "scope_key",
        "created_at",
        "current_tier",
        "requested_tier",
        "expansion_trigger",
        "sufficiency_before",
        "authority_sources_considered",
        "opened_items",
        "rejected_items",
        "omitted_items",
        "token_budget_before",
        "token_budget_after",
        "budget_state",
        "retrieval_path_pointer",
        "decision_result",
        "decision_reason",
        "lifecycle_state",
    }
    missing = sorted(required.difference(record))
    if missing:
        raise ValueError(f"context expansion record missing fields: {', '.join(missing)}")
    if record["schema_version"] != "0.1":
        raise ValueError("unsupported context expansion schema version")
    if record["current_tier"] not in TIERS or record["requested_tier"] not in TIERS:
        raise ValueError("unsupported context tier")
    if record["expansion_trigger"] not in TRIGGERS:
        raise ValueError("unsupported expansion trigger")
    if record["sufficiency_before"] not in SUFFICIENCY_VERDICTS:
        raise ValueError("unsupported sufficiency verdict")
    if record["decision_result"] not in DECISION_RESULTS:
        raise ValueError("unsupported expansion decision")
    if record["lifecycle_state"] not in LIFECYCLE_STATES:
        raise ValueError("unsupported lifecycle state")
    if not isinstance(record["decision_reason"], str) or not record["decision_reason"].strip():
        raise ValueError("decision_reason must be non-empty")
    if not isinstance(record["token_budget_before"], int) or record["token_budget_before"] < 0:
        raise ValueError("token_budget_before must be a non-negative integer")
    if not isinstance(record["token_budget_after"], int) or record["token_budget_after"] < 0:
        raise ValueError("token_budget_after must be a non-negative integer")

    if (
        record["expansion_trigger"] == "SUFFICIENCY_FAILED"
        and record["sufficiency_before"] not in {"INSUFFICIENT", "UNKNOWN", "BLOCKED"}
    ):
        raise ValueError("CEDR_MISSING_SUFFICIENCY")
    if record["token_budget_after"] > record["token_budget_before"] and not record.get("budget_approval_pointer"):
        raise ValueError("CEDR_UNAPPROVED_BUDGET_INCREASE")
    if (
        TIERS[record["requested_tier"]] < TIERS[record["current_tier"]]
        and record["expansion_trigger"] != "COMPACTION_RESET"
    ):
        raise ValueError("CEDR_ILLEGAL_TIER_TRANSITION")
    if record["decision_result"] == "EXPANDED" and TIERS[record["requested_tier"]] <= TIERS[record["current_tier"]]:
        raise ValueError("EXPANDED requires a deeper requested tier")
    if record["decision_result"] == "NO_OP" and record["requested_tier"] != record["current_tier"]:
        raise ValueError("NO_OP requires an unchanged tier")

    for field_name in ("authority_sources_considered", "opened_items", "rejected_items", "omitted_items"):
        if not isinstance(record[field_name], list):
            raise ValueError(f"{field_name} must be a list")
    for pointer in record["authority_sources_considered"]:
        if not isinstance(pointer, dict) or not pointer.get("source_system") or not pointer.get("source_object_id"):
            raise ValueError("authority source requires a source pointer")
        if pointer.get("coverage_state") not in {"RESOLVED", "UNRESOLVED", "PARTIAL", "INACCESSIBLE"}:
            raise ValueError("unsupported source coverage state")
    for item in record["opened_items"] + record["rejected_items"] + record["omitted_items"]:
        if not isinstance(item, dict) or not item.get("reason"):
            raise ValueError("opened, rejected, and omitted items require reasons")
        pointer = item.get("source_pointer")
        if not isinstance(pointer, dict) or not pointer.get("source_system") or not pointer.get("source_object_id"):
            raise ValueError("context item requires a source pointer")
        if pointer.get("coverage_state") not in {"RESOLVED", "UNRESOLVED", "PARTIAL", "INACCESSIBLE"}:
            raise ValueError("unsupported source coverage state")
