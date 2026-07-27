"""Exact, evidence-backed cross-source identity resolution."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any
from uuid import UUID, uuid5

CROSS_SOURCE_IDENTITY_NAMESPACE = UUID("86ab1db2-f943-4dc3-a8d6-77af74378dbf")


@dataclass(frozen=True)
class ExactIdentityBinding:
    notion_source_object_id: str
    drive_source_object_id: str
    evidence_pointer: str
    binding_key: str


def cross_source_entity_id(binding: ExactIdentityBinding) -> str:
    canonical = (
        "aios-cross-source-entity:"
        f"notion:{binding.notion_source_object_id}:"
        f"google_drive:{binding.drive_source_object_id}:"
        f"{binding.binding_key}:{binding.evidence_pointer}"
    )
    return str(uuid5(CROSS_SOURCE_IDENTITY_NAMESPACE, canonical))


def resolve_exact_identities(
    notion_snapshot: dict[str, Any],
    drive_snapshot: dict[str, Any],
    bindings: list[ExactIdentityBinding],
) -> dict[str, Any]:
    """Resolve only explicit bindings. Labels and paths never create identity."""
    notion_by_source = {
        node["source_object_id"]: node for node in notion_snapshot.get("nodes", [])
        if node.get("source_system") == "notion"
    }
    drive_by_source = {
        node["source_object_id"]: node for node in drive_snapshot.get("nodes", [])
        if node.get("source_system") == "google_drive"
    }

    resolved: list[dict[str, Any]] = []
    unresolved: list[dict[str, Any]] = []
    seen_notion: set[str] = set()
    seen_drive: set[str] = set()

    for binding in sorted(bindings, key=lambda item: (item.notion_source_object_id, item.drive_source_object_id)):
        if binding.notion_source_object_id in seen_notion or binding.drive_source_object_id in seen_drive:
            raise ValueError("Cross-source binding is not one-to-one")
        seen_notion.add(binding.notion_source_object_id)
        seen_drive.add(binding.drive_source_object_id)
        notion_node = notion_by_source.get(binding.notion_source_object_id)
        drive_node = drive_by_source.get(binding.drive_source_object_id)
        missing = []
        if notion_node is None:
            missing.append("notion")
        if drive_node is None:
            missing.append("google_drive")
        if missing:
            unresolved.append({
                "binding_key": binding.binding_key,
                "notion_source_object_id": binding.notion_source_object_id,
                "drive_source_object_id": binding.drive_source_object_id,
                "missing_sources": missing,
                "evidence_pointer": binding.evidence_pointer,
                "state": "UNRESOLVED",
            })
            continue
        resolved.append({
            "entity_id": cross_source_entity_id(binding),
            "binding_key": binding.binding_key,
            "notion_node_id": notion_node["node_id"],
            "drive_node_id": drive_node["node_id"],
            "notion_source_object_id": binding.notion_source_object_id,
            "drive_source_object_id": binding.drive_source_object_id,
            "evidence_pointer": binding.evidence_pointer,
            "resolution_method": "EXACT_REGISTERED_BINDING",
            "confidence": 1.0,
            "state": "RESOLVED",
        })

    return {
        "resolution_version": "0.1",
        "notion_snapshot_id": notion_snapshot["snapshot_id"],
        "drive_snapshot_id": drive_snapshot["snapshot_id"],
        "resolved": resolved,
        "unresolved": unresolved,
    }
