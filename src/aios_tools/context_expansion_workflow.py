from __future__ import annotations

from typing import Any

from .cognition_receipt import CognitionReceiptBuilder, validate_cognition_receipt
from .context_expansion import SufficiencyAssessment, build_context_expansion_decision
from .retrieval_trajectory import validate_retrieval_trajectory

WORKFLOW_ID = "context-expansion.packet-read-only"
WORKFLOW_VERSION = "0.1"
ACTOR = "aios-tools.context-expansion-workflow"


def _cedr_evidence_pointer(record: dict[str, Any]) -> dict[str, Any]:
    return {
        "evidence_type": "CONTEXT_EXPANSION_DECISION_RECORD",
        "evidence_id": record["expansion_record_id"],
        "schema_version": record["schema_version"],
        "scope_key": record["scope_key"],
        "lifecycle_state": record["lifecycle_state"],
        "authority_transfer": False,
    }


def run_context_expansion_packet_workflow(
    *,
    request_id: str,
    trajectory: dict[str, Any],
    assessment: SufficiencyAssessment | dict[str, Any],
    started_at: str,
    completed_at: str,
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
    provenance: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Run one bounded read-only packet decision and emit correlated evidence.

    This workflow accepts an already-built Retrieval Trajectory. It performs no
    source retrieval, connector call, durable write, authority resolution, or
    capability registration. The resulting CEDR is referenced by ID on the
    Cognition Receipt event evidence surface rather than embedded as raw content.
    """
    if not isinstance(request_id, str) or not request_id.strip():
        raise ValueError("request_id must be non-empty")

    validate_retrieval_trajectory(trajectory)
    trajectory_id = trajectory.get("trajectory_id")
    if not isinstance(trajectory_id, str) or not trajectory_id.startswith("rt_"):
        raise ValueError("workflow requires a finalized retrieval trajectory")

    record = build_context_expansion_decision(
        trajectory=trajectory,
        assessment=assessment,
        created_at=completed_at,
        current_tier=current_tier,
        requested_tier=requested_tier,
        expansion_trigger=expansion_trigger,
        token_budget_before=token_budget_before,
        token_budget_after=token_budget_after,
        decision_result=decision_result,
        decision_reason=decision_reason,
        lifecycle_state=lifecycle_state,
        budget_approval_pointer=budget_approval_pointer,
        omitted_items=omitted_items,
    )
    evidence_pointer = _cedr_evidence_pointer(record)

    builder = CognitionReceiptBuilder(
        trace_id=f"trace-{request_id}",
        request_id=request_id,
        scope_key=trajectory["scope_key"],
        mode="READ_ONLY",
        started_at=started_at,
    )
    builder.append(
        "intent.received",
        started_at,
        "workflow-requester",
        {"request_kind": "context_expansion_packet_decision", "workflow_id": WORKFLOW_ID},
    )
    builder.append(
        "intent.classified",
        started_at,
        ACTOR,
        {"intent_class": "bounded_read_only_packet_workflow", "workflow_version": WORKFLOW_VERSION},
    )
    builder.append(
        "scope.candidate_considered",
        started_at,
        ACTOR,
        {"scope_key": trajectory["scope_key"], "source": "retrieval_trajectory"},
    )
    builder.append(
        "scope.resolved",
        started_at,
        ACTOR,
        {"scope_key": trajectory["scope_key"], "resolution": "trajectory_scope"},
    )

    for event in trajectory["events"]:
        evidence = [evidence_pointer] if event["event_type"] == "context.packet_composed" else None
        builder.append(
            event["event_type"],
            completed_at,
            ACTOR,
            dict(event["payload"]),
            evidence=evidence,
        )

    builder.append(
        "outcome.observed",
        completed_at,
        ACTOR,
        {
            "workflow_id": WORKFLOW_ID,
            "decision_result": record["decision_result"],
            "expansion_record_id": record["expansion_record_id"],
        },
        evidence=[evidence_pointer],
    )
    builder.append(
        "receipt.created",
        completed_at,
        ACTOR,
        {"receipt_kind": "context_expansion_packet_workflow", "request_id": request_id},
        evidence=[evidence_pointer],
    )
    receipt = builder.finalize(
        completed_at=completed_at,
        status="COMPLETED",
        provenance=list(provenance or []),
    )

    result = {
        "workflow_id": WORKFLOW_ID,
        "workflow_version": WORKFLOW_VERSION,
        "scope_key": trajectory["scope_key"],
        "status": "COMPLETED",
        "context_expansion_decision": record,
        "cognition_receipt": receipt,
        "external_effects": [],
        "authority_transfer": False,
    }
    validate_context_expansion_workflow_result(result)
    return result


def validate_context_expansion_workflow_result(result: dict[str, Any]) -> None:
    if result.get("workflow_id") != WORKFLOW_ID or result.get("workflow_version") != WORKFLOW_VERSION:
        raise ValueError("unsupported context expansion workflow identity")
    if result.get("status") != "COMPLETED":
        raise ValueError("context expansion workflow result must be completed")
    if result.get("external_effects"):
        raise ValueError("context expansion workflow is read-only")
    if result.get("authority_transfer") is not False:
        raise ValueError("context expansion workflow cannot transfer authority")

    record = result.get("context_expansion_decision")
    receipt = result.get("cognition_receipt")
    if not isinstance(record, dict) or not isinstance(receipt, dict):
        raise ValueError("workflow result requires a CEDR and Cognition Receipt")
    if record.get("scope_key") != result.get("scope_key") or receipt.get("scope_key") != result.get("scope_key"):
        raise ValueError("workflow artifacts must share one scope")

    events = receipt.get("events")
    if not isinstance(events, list):
        raise ValueError("Cognition Receipt requires an event list")
    record_id = record.get("expansion_record_id")
    evidence = [item for event in events for item in event.get("evidence", [])]
    matching = [item for item in evidence if item.get("evidence_id") == record_id]
    if not matching:
        raise ValueError("Cognition Receipt must reference the CEDR on its evidence surface")
    if any("context_expansion_decision" in item for item in evidence):
        raise ValueError("Cognition Receipt evidence must contain a pointer, not an embedded CEDR")
    if any(item.get("authority_transfer") is not False for item in matching):
        raise ValueError("CEDR evidence pointer cannot transfer authority")

    validate_cognition_receipt(receipt)
