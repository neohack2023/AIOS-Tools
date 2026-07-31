from __future__ import annotations

from typing import Any

from .canonical import canonical_sha256
from .context_expansion import validate_context_expansion_decision
from .context_expansion_workflow import (
    WORKFLOW_ID,
    WORKFLOW_VERSION,
    validate_context_expansion_workflow_result,
)

PROJECTION_KIND = "CONTEXT_EXPANSION_OBSERVATORY"
PROJECTION_VERSION = "0.1"

_TOP_LEVEL_KEYS = {
    "projection_id",
    "projection_version",
    "projection_kind",
    "observed_at",
    "scope_key",
    "workflow",
    "identities",
    "context_expansion",
    "evidence_links",
    "privacy",
    "external_effects",
    "authority_transfer",
}
_WORKFLOW_KEYS = {
    "workflow_id",
    "workflow_version",
    "status",
    "mode",
    "started_at",
    "completed_at",
    "event_count",
}
_IDENTITY_KEYS = {
    "request_id",
    "trace_id",
    "receipt_id",
    "execution_id",
    "trajectory_id",
    "context_packet_id",
    "expansion_record_id",
}
_CONTEXT_KEYS = {
    "current_tier",
    "requested_tier",
    "tier_movement",
    "sufficiency_verdict",
    "expansion_trigger",
    "decision_result",
    "budget_state",
    "lifecycle_state",
}
_EVIDENCE_KEYS = {
    "evidence_type",
    "evidence_id",
    "schema_version",
    "scope_key",
    "lifecycle_state",
    "authority_transfer",
    "referenced_by_event_types",
}
_PRIVACY_KEYS = {
    "source_content_included",
    "event_payloads_included",
    "raw_receipt_included",
    "raw_cedr_included",
}
_FORBIDDEN_KEYS = {
    "events",
    "payload",
    "context_expansion_decision",
    "cognition_receipt",
    "opened_items",
    "rejected_items",
    "omitted_items",
    "authority_sources_considered",
    "decision_reason",
    "source_content",
    "prompt",
    "embedding",
    "vector",
}


def _projection_id(value: dict[str, Any]) -> str:
    payload = {key: item for key, item in value.items() if key != "projection_id"}
    return f"op_{canonical_sha256(payload)}"


def _assert_exact_keys(value: dict[str, Any], expected: set[str], label: str) -> None:
    actual = set(value)
    if actual != expected:
        missing = sorted(expected.difference(actual))
        extra = sorted(actual.difference(expected))
        detail = []
        if missing:
            detail.append(f"missing={','.join(missing)}")
        if extra:
            detail.append(f"extra={','.join(extra)}")
        raise ValueError(f"{label} keys do not match the read-model contract: {'; '.join(detail)}")


def _reject_forbidden_keys(value: Any) -> None:
    if isinstance(value, dict):
        forbidden = sorted(_FORBIDDEN_KEYS.intersection(value))
        if forbidden:
            raise ValueError(f"Observatory projection contains forbidden raw fields: {', '.join(forbidden)}")
        for item in value.values():
            _reject_forbidden_keys(item)
    elif isinstance(value, list):
        for item in value:
            _reject_forbidden_keys(item)


def _content_free_evidence_links(
    *,
    receipt: dict[str, Any],
    expansion_record_id: str,
) -> list[dict[str, Any]]:
    grouped: dict[tuple[str, str, str, str, str, bool], set[str]] = {}
    for event in receipt["events"]:
        for pointer in event.get("evidence", []):
            if pointer.get("evidence_id") != expansion_record_id:
                continue
            key = (
                pointer.get("evidence_type"),
                pointer.get("evidence_id"),
                pointer.get("schema_version"),
                pointer.get("scope_key"),
                pointer.get("lifecycle_state"),
                pointer.get("authority_transfer"),
            )
            if any(item is None for item in key):
                raise ValueError("CEDR evidence pointer is incomplete")
            grouped.setdefault(key, set()).add(event["event_type"])

    links = [
        {
            "evidence_type": key[0],
            "evidence_id": key[1],
            "schema_version": key[2],
            "scope_key": key[3],
            "lifecycle_state": key[4],
            "authority_transfer": key[5],
            "referenced_by_event_types": sorted(event_types),
        }
        for key, event_types in grouped.items()
    ]
    links.sort(key=lambda item: (item["evidence_type"], item["evidence_id"]))
    if not links:
        raise ValueError("Observatory projection requires a content-free CEDR evidence link")
    return links


def build_context_expansion_observatory_projection(
    workflow_result: dict[str, Any],
) -> dict[str, Any]:
    """Project one merged read-only workflow result into an Observatory read model.

    The projection is a deterministic metadata view. It does not execute the
    workflow, retrieve source content, copy receipt events or payloads, register a
    capability, call a connector, or create a durable write surface.
    """
    validate_context_expansion_workflow_result(workflow_result)

    record = workflow_result["context_expansion_decision"]
    receipt = workflow_result["cognition_receipt"]
    validate_context_expansion_decision(record)
    if receipt.get("mode") != "READ_ONLY":
        raise ValueError("Observatory projection requires a READ_ONLY Cognition Receipt")

    execution_id = workflow_result.get("execution_id")
    if execution_id is not None and (not isinstance(execution_id, str) or not execution_id.strip()):
        raise ValueError("execution_id must be a non-empty string when present")

    evidence_links = _content_free_evidence_links(
        receipt=receipt,
        expansion_record_id=record["expansion_record_id"],
    )
    projection = {
        "projection_version": PROJECTION_VERSION,
        "projection_kind": PROJECTION_KIND,
        "observed_at": receipt["completed_at"],
        "scope_key": workflow_result["scope_key"],
        "workflow": {
            "workflow_id": workflow_result["workflow_id"],
            "workflow_version": workflow_result["workflow_version"],
            "status": workflow_result["status"],
            "mode": receipt["mode"],
            "started_at": receipt["started_at"],
            "completed_at": receipt["completed_at"],
            "event_count": len(receipt["events"]),
        },
        "identities": {
            "request_id": receipt["request_id"],
            "trace_id": receipt["trace_id"],
            "receipt_id": receipt["receipt_id"],
            "execution_id": execution_id,
            "trajectory_id": record["retrieval_path_pointer"].get("trajectory_id"),
            "context_packet_id": record["packet_id"],
            "expansion_record_id": record["expansion_record_id"],
        },
        "context_expansion": {
            "current_tier": record["current_tier"],
            "requested_tier": record["requested_tier"],
            "tier_movement": f"{record['current_tier']}->{record['requested_tier']}",
            "sufficiency_verdict": record["sufficiency_before"],
            "expansion_trigger": record["expansion_trigger"],
            "decision_result": record["decision_result"],
            "budget_state": record["budget_state"],
            "lifecycle_state": record["lifecycle_state"],
        },
        "evidence_links": evidence_links,
        "privacy": {
            "source_content_included": False,
            "event_payloads_included": False,
            "raw_receipt_included": False,
            "raw_cedr_included": False,
        },
        "external_effects": [],
        "authority_transfer": False,
    }
    projection["projection_id"] = _projection_id(projection)
    validate_observatory_projection(projection)
    return projection


def validate_observatory_projection(projection: dict[str, Any]) -> None:
    if not isinstance(projection, dict):
        raise ValueError("Observatory projection must be an object")
    _reject_forbidden_keys(projection)
    _assert_exact_keys(projection, _TOP_LEVEL_KEYS, "Observatory projection")

    if projection["projection_version"] != PROJECTION_VERSION:
        raise ValueError("unsupported Observatory projection version")
    if projection["projection_kind"] != PROJECTION_KIND:
        raise ValueError("unsupported Observatory projection kind")
    if projection["external_effects"] != []:
        raise ValueError("Observatory projection is read-only")
    if projection["authority_transfer"] is not False:
        raise ValueError("Observatory projection cannot transfer authority")
    if projection["projection_id"] != _projection_id(projection):
        raise ValueError("Observatory projection ID does not match canonical content")

    workflow = projection["workflow"]
    identities = projection["identities"]
    context = projection["context_expansion"]
    privacy = projection["privacy"]
    if not all(isinstance(value, dict) for value in (workflow, identities, context, privacy)):
        raise ValueError("Observatory projection sections must be objects")
    _assert_exact_keys(workflow, _WORKFLOW_KEYS, "workflow projection")
    _assert_exact_keys(identities, _IDENTITY_KEYS, "identity projection")
    _assert_exact_keys(context, _CONTEXT_KEYS, "context expansion projection")
    _assert_exact_keys(privacy, _PRIVACY_KEYS, "privacy projection")

    if workflow["workflow_id"] != WORKFLOW_ID or workflow["workflow_version"] != WORKFLOW_VERSION:
        raise ValueError("Observatory projection references an unsupported workflow")
    if workflow["mode"] != "READ_ONLY":
        raise ValueError("Observatory projection workflow mode must be READ_ONLY")
    if workflow["status"] != "COMPLETED":
        raise ValueError("Observatory projection requires a completed workflow")
    if not isinstance(workflow["event_count"], int) or workflow["event_count"] < 1:
        raise ValueError("Observatory projection event_count must be positive")

    required_identity_strings = (
        "request_id",
        "trace_id",
        "receipt_id",
        "trajectory_id",
        "context_packet_id",
        "expansion_record_id",
    )
    for field in required_identity_strings:
        if not isinstance(identities[field], str) or not identities[field].strip():
            raise ValueError(f"identity {field} must be non-empty")
    if identities["execution_id"] is not None and (
        not isinstance(identities["execution_id"], str) or not identities["execution_id"].strip()
    ):
        raise ValueError("identity execution_id must be null or non-empty")

    expected_movement = f"{context['current_tier']}->{context['requested_tier']}"
    if context["tier_movement"] != expected_movement:
        raise ValueError("tier_movement does not match the projected tiers")

    links = projection["evidence_links"]
    if not isinstance(links, list) or not links:
        raise ValueError("Observatory projection requires evidence links")
    for link in links:
        if not isinstance(link, dict):
            raise ValueError("Observatory evidence link must be an object")
        _assert_exact_keys(link, _EVIDENCE_KEYS, "Observatory evidence link")
        if link["evidence_id"] != identities["expansion_record_id"]:
            raise ValueError("Observatory evidence link must reference the projected CEDR")
        if link["scope_key"] != projection["scope_key"]:
            raise ValueError("Observatory evidence link scope must match the projection")
        if link["authority_transfer"] is not False:
            raise ValueError("Observatory evidence link cannot transfer authority")
        if not isinstance(link["referenced_by_event_types"], list) or not link["referenced_by_event_types"]:
            raise ValueError("Observatory evidence link requires event-type references")

    if any(value is not False for value in privacy.values()):
        raise ValueError("Observatory privacy flags must remain false")
