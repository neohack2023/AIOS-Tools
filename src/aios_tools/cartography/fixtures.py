"""Deterministic read-only fixture adapters for Cartography Slice 2."""

from __future__ import annotations

from copy import deepcopy
from typing import Any

from .graph_ir import edge_id_for, node_id_for

ADAPTER_VERSIONS = {
    "notion.page_tree": "0.1.0",
    "drive.file_tree": "0.1.0",
    "registry.project_scope": "0.1.0",
    "registry.capability": "0.1.0",
}


def _node(source_system: str, object_type: str, object_id: str, label: str, pointer: str,
          node_type: str, scope_key: str, authority_role: str, attributes: dict[str, Any] | None = None,
          parent_node_id: str | None = None) -> dict[str, Any]:
    node = {
        "node_id": node_id_for(source_system, object_type, object_id),
        "node_type": node_type,
        "label": label,
        "scope_key": scope_key,
        "source_system": source_system,
        "source_object_type": object_type,
        "source_object_id": object_id,
        "source_pointer": pointer,
        "authority_role": authority_role,
        "lifecycle_state": "ACTIVE",
        "verification_state": "PASSED",
        "freshness_state": "CURRENT",
        "attributes": deepcopy(attributes or {}),
    }
    if parent_node_id:
        node["parent_node_id"] = parent_node_id
    return node


def _edge(relation: str, source: str, target: str, pointer: str, scope_key: str,
          authority_role: str = "DERIVED_VIEW", evidence_state: str = "DIRECT_SOURCE") -> dict[str, Any]:
    return {
        "edge_id": edge_id_for(relation, source, target, pointer),
        "relation_type": relation,
        "source_node_id": source,
        "target_node_id": target,
        "directionality": "DIRECTED",
        "scope_key": scope_key,
        "source_pointer": pointer,
        "authority_role": authority_role,
        "evidence_state": evidence_state,
        "explanation": f"Fixture mapping for {relation}",
        "attributes": {},
    }


def adapt_notion_page_tree(records: list[dict[str, Any]], scope_key: str) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
    nodes, edges, unresolved = [], [], []
    by_id: dict[str, str] = {}
    for record in sorted(records, key=lambda item: item["id"]):
        node = _node("notion", record.get("type", "page"), record["id"], record["title"], record["url"],
                     "knowledge_object", scope_key, record.get("authority_role", "AUTHORITATIVE"),
                     {"partial": bool(record.get("partial", False))})
        nodes.append(node)
        by_id[record["id"]] = node["node_id"]
    for record in records:
        parent = record.get("parent_id")
        if parent and parent in by_id:
            edges.append(_edge("contains", by_id[parent], by_id[record["id"]], record["url"], scope_key))
        elif parent:
            unresolved.append({"raw_value": parent, "expected_relation": "contains", "source_node_id": by_id[record["id"]],
                               "target_selector": {"source_object_id": parent}, "reason": "parent_not_in_fixture",
                               "evidence_state": "UNRESOLVED", "source_pointer": record["url"]})
    return nodes, edges, unresolved


def adapt_drive_tree(records: list[dict[str, Any]], scope_key: str) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
    nodes, edges, unresolved = [], [], []
    by_id: dict[str, str] = {}
    for record in sorted(records, key=lambda item: item["id"]):
        node = _node("google_drive", record["type"], record["id"], record["name"], record["url"],
                     record["type"], scope_key, record.get("authority_role", "DRIVE_SHADOW"),
                     {"coverage_state": record.get("coverage_state", "COMPLETE")})
        nodes.append(node)
        by_id[record["id"]] = node["node_id"]
    for record in records:
        parent = record.get("parent_id")
        if parent and parent in by_id:
            edges.append(_edge("contains", by_id[parent], by_id[record["id"]], record["url"], scope_key, "DRIVE_SHADOW"))
        elif parent:
            unresolved.append({"raw_value": parent, "expected_relation": "contains", "source_node_id": by_id[record["id"]],
                               "target_selector": {"source_object_id": parent}, "reason": "parent_not_in_fixture",
                               "evidence_state": "UNRESOLVED", "source_pointer": record["url"]})
    return nodes, edges, unresolved


def adapt_scope_registry(rows: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
    nodes, edges, unresolved = [], [], []
    by_key: dict[str, str] = {}
    for row in sorted(rows, key=lambda item: item["scope_key"]):
        node = _node("project_scope_registry", "scope_row", row["scope_key"], row["label"], row["source_pointer"],
                     "scope", row["scope_key"], "AUTHORITATIVE", {"aliases": sorted(row.get("aliases", []))})
        nodes.append(node)
        by_key[row["scope_key"]] = node["node_id"]
    for row in rows:
        parent = row.get("parent_scope")
        if parent and parent in by_key:
            edges.append(_edge("belongs_to_scope", by_key[row["scope_key"]], by_key[parent], row["source_pointer"], row["scope_key"], "AUTHORITATIVE", "REGISTERED_BINDING"))
        elif parent:
            unresolved.append({"raw_value": parent, "expected_relation": "belongs_to_scope", "source_node_id": by_key[row["scope_key"]],
                               "target_selector": {"scope_key": parent}, "reason": "scope_not_registered",
                               "evidence_state": "UNRESOLVED", "source_pointer": row["source_pointer"]})
    return nodes, edges, unresolved


def adapt_capability_registry(rows: list[dict[str, Any]], known_scopes: dict[str, str]) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
    nodes, edges, unresolved = [], [], []
    for row in sorted(rows, key=lambda item: item["capability_id"]):
        node = _node("capability_registry", "capability_row", row["capability_id"], row["label"], row["source_pointer"],
                     "capability", row["scope_key"], "AUTHORITATIVE", {"mode": row.get("mode", "READ_ONLY")})
        nodes.append(node)
        scope_node = known_scopes.get(row["scope_key"])
        if scope_node:
            edges.append(_edge("belongs_to_scope", node["node_id"], scope_node, row["source_pointer"], row["scope_key"], "AUTHORITATIVE", "REGISTERED_BINDING"))
        else:
            unresolved.append({"raw_value": row["scope_key"], "expected_relation": "belongs_to_scope", "source_node_id": node["node_id"],
                               "target_selector": {"scope_key": row["scope_key"]}, "reason": "scope_not_registered",
                               "evidence_state": "UNRESOLVED", "source_pointer": row["source_pointer"]})
    return nodes, edges, unresolved
