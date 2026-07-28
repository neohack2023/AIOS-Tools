from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from .canonical import canonical_sha256

EVENT_TYPES = {
    "intent.received",
    "intent.classified",
    "scope.candidate_considered",
    "scope.resolved",
    "authority.candidate_considered",
    "authority.selected",
    "retrieval.packet_considered",
    "retrieval.packet_selected",
    "retrieval.packet_rejected",
    "conflict.detected",
    "conflict.resolution_proposed",
    "context.packet_composed",
    "answer.generated",
    "outcome.observed",
}


def _event_id(event: dict[str, Any]) -> str:
    payload = {key: value for key, value in event.items() if key != "event_id"}
    return f"ce_{canonical_sha256(payload)}"


def _receipt_id(receipt: dict[str, Any]) -> str:
    payload = {key: value for key, value in receipt.items() if key != "receipt_id"}
    return f"cr_{canonical_sha256(payload)}"


@dataclass
class CognitionReceiptBuilder:
    trace_id: str
    request_id: str
    scope_key: str
    mode: str
    started_at: str
    events: list[dict[str, Any]] = field(default_factory=list)

    def append(
        self,
        event_type: str,
        occurred_at: str,
        actor: str,
        payload: dict[str, Any],
        evidence: list[dict[str, Any]] | None = None,
    ) -> dict[str, Any]:
        event = {
            "sequence": len(self.events),
            "event_type": event_type,
            "occurred_at": occurred_at,
            "actor": actor,
            "scope_key": self.scope_key,
            "payload": payload,
            "evidence": evidence or [],
        }
        event["event_id"] = _event_id(event)
        self.events.append(event)
        return event

    def finalize(
        self,
        *,
        completed_at: str,
        status: str,
        provenance: list[dict[str, Any]] | None = None,
    ) -> dict[str, Any]:
        receipt = {
            "receipt_version": "0.1",
            "trace_id": self.trace_id,
            "request_id": self.request_id,
            "scope_key": self.scope_key,
            "mode": self.mode,
            "started_at": self.started_at,
            "completed_at": completed_at,
            "status": status,
            "events": list(self.events),
            "provenance": provenance or [],
            "external_effects": [],
            "authority_transfer": False,
        }
        validate_cognition_receipt(receipt)
        receipt["receipt_id"] = _receipt_id(receipt)
        return receipt


def validate_cognition_receipt(receipt: dict[str, Any]) -> None:
    if receipt.get("mode") not in {"READ_ONLY", "SIMULATION", "REPLAY"}:
        raise ValueError("unsupported cognition receipt mode")
    if receipt.get("status") not in {"COMPLETED", "FAILED", "BLOCKED"}:
        raise ValueError("unsupported cognition receipt status")
    if receipt.get("external_effects"):
        raise ValueError("cognition receipt slice is read-only")
    if receipt.get("authority_transfer") is not False:
        raise ValueError("authority transfer is forbidden")

    events = receipt.get("events", [])
    seen_ids: set[str] = set()
    seen_types: list[str] = []
    considered_scopes: set[str] = set()
    considered_authorities: set[str] = set()
    considered_packets: set[str] = set()
    selected_packets: set[str] = set()
    composed_packet_ids: set[str] = set()

    for index, event in enumerate(events):
        if event.get("sequence") != index:
            raise ValueError("event sequence must be contiguous")
        if event.get("scope_key") != receipt.get("scope_key"):
            raise ValueError("event scope must match receipt scope")
        if event.get("event_type") not in EVENT_TYPES:
            raise ValueError("unknown cognition event type")
        expected_id = _event_id(event)
        if event.get("event_id") != expected_id:
            raise ValueError("event ID does not match canonical payload")
        if expected_id in seen_ids:
            raise ValueError("duplicate cognition event ID")
        seen_ids.add(expected_id)

        event_type = event["event_type"]
        payload = event.get("payload", {})
        seen_types.append(event_type)

        if event_type == "scope.candidate_considered":
            considered_scopes.add(payload.get("scope_key", ""))
        elif event_type == "scope.resolved":
            if payload.get("scope_key") not in considered_scopes:
                raise ValueError("resolved scope must have been considered")
        elif event_type == "authority.candidate_considered":
            considered_authorities.add(payload.get("authority_id", ""))
        elif event_type == "authority.selected":
            if payload.get("authority_id") not in considered_authorities:
                raise ValueError("selected authority must have been considered")
        elif event_type == "retrieval.packet_considered":
            considered_packets.add(payload.get("packet_id", ""))
        elif event_type in {"retrieval.packet_selected", "retrieval.packet_rejected"}:
            packet_id = payload.get("packet_id")
            if packet_id not in considered_packets:
                raise ValueError("packet decision requires prior consideration")
            if event_type == "retrieval.packet_selected":
                selected_packets.add(packet_id)
        elif event_type == "context.packet_composed":
            referenced = set(payload.get("packet_ids", []))
            if not referenced.issubset(selected_packets):
                raise ValueError("composed context may reference only selected packets")
            composed_packet_ids.add(payload.get("context_packet_id", ""))
        elif event_type == "answer.generated":
            if payload.get("context_packet_id") not in composed_packet_ids:
                raise ValueError("answer requires a composed context packet")

    if "intent.received" not in seen_types:
        raise ValueError("receipt requires intent.received")
    if "answer.generated" in seen_types and "context.packet_composed" not in seen_types:
        raise ValueError("answer generation requires packet composition")
