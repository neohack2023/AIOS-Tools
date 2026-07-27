"""Deterministic non-rendered View Spec compilation for Cartography Slice 2."""

from __future__ import annotations

from typing import Any

SYSTEM_OVERVIEW_VIEW = {
    "view_id": "system-overview-v0.1",
    "title": "AIOS System Overview",
    "root_selector": {"scope_key": "global-working-memory"},
    "lod": [0, 1],
    "include_node_types": ["scope", "authority_surface", "registry", "governance_system", "observatory", "cartography_engine"],
    "exclude_node_types": ["record", "event", "receipt"],
    "include_relations": ["contains", "belongs_to_scope", "reads_from", "writes_to", "authorizes", "implemented_by"],
}

WORKFLOW_CONTROL_PLANE_VIEW = {
    "view_id": "workflow-control-plane-v0.1",
    "title": "AIOS Workflow Control Plane",
    "root_selector": {"labels": ["AI_MEMORY_OS Observatory", "Cartography Engine"]},
    "lod": [1, 2],
    "include_node_types": ["workflow", "capability", "registry", "governance_system", "observatory", "cartography_engine"],
    "exclude_node_types": ["repository_code_object"],
    "include_relations": ["invokes", "routes_to", "reads_from", "writes_to", "validates", "depends_on", "implemented_by"],
}


def compile_view(snapshot: dict[str, Any], view_spec: dict[str, Any]) -> dict[str, Any]:
    """Compile stable included node and edge IDs without layout or rendering."""
    include_types = set(view_spec.get("include_node_types", []))
    exclude_types = set(view_spec.get("exclude_node_types", []))
    include_relations = set(view_spec.get("include_relations", []))

    included_nodes = [
        node for node in snapshot.get("nodes", [])
        if (not include_types or node.get("node_type") in include_types)
        and node.get("node_type") not in exclude_types
    ]
    node_ids = {node["node_id"] for node in included_nodes}
    included_edges = [
        edge for edge in snapshot.get("edges", [])
        if edge.get("relation_type") in include_relations
        and edge.get("source_node_id") in node_ids
        and edge.get("target_node_id") in node_ids
    ]
    return {
        "view_id": view_spec["view_id"],
        "included_node_ids": sorted(node_ids),
        "included_edge_ids": sorted(edge["edge_id"] for edge in included_edges),
        "excluded_node_count": len(snapshot.get("nodes", [])) - len(included_nodes),
        "excluded_edge_count": len(snapshot.get("edges", [])) - len(included_edges),
    }
