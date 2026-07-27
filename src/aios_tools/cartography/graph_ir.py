"""Deterministic identity and semantic validation for AIOS Graph IR v0.1."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable
from uuid import UUID, uuid5
import json

from jsonschema import Draft202012Validator, FormatChecker

AIOS_NODE_NAMESPACE = UUID("75ce2446-3d66-5d41-9a8b-5fd379c1e2bf")
AIOS_EDGE_NAMESPACE = UUID("08c75efa-90c8-5d93-9938-f5fda58e4ab5")

DERIVED_EVIDENCE_STATES = {"DERIVED_RULE", "INFERRED_ANALYSIS"}
RENDERER_ONLY_KEYS = {
    "x",
    "y",
    "z",
    "position",
    "coordinates",
    "camera",
    "camera_state",
    "renderer",
    "renderer_state",
    "layout",
    "layout_state",
    "manual_overlay",
    "manual_overlays",
    "pinned_position",
}


@dataclass(frozen=True)
class GraphIRError:
    code: str
    message: str
    pointer: str


def node_id_for(source_system: str, source_object_type: str, source_object_id: str) -> str:
    """Return the governed UUIDv5 identity for a source-backed node."""
    canonical_name = f"aios-node:{source_system}:{source_object_type}:{source_object_id}"
    return str(uuid5(AIOS_NODE_NAMESPACE, canonical_name))


def edge_id_for(
    relation_type: str,
    source_node_id: str,
    target_node_id: str,
    source_pointer_or_evidence_key: str,
) -> str:
    """Return the governed UUIDv5 identity for an edge and its exact evidence."""
    canonical_name = (
        f"aios-edge:{relation_type}:{source_node_id}:"
        f"{target_node_id}:{source_pointer_or_evidence_key}"
    )
    return str(uuid5(AIOS_EDGE_NAMESPACE, canonical_name))


def _schema_path() -> Path:
    return Path(__file__).resolve().parents[3] / "contracts" / "cartography" / "graph-ir.v0.1.schema.json"


def _load_schema() -> dict[str, Any]:
    with _schema_path().open("r", encoding="utf-8") as handle:
        return json.load(handle)


def _walk_keys(value: Any, pointer: str = "") -> Iterable[tuple[str, str]]:
    if isinstance(value, dict):
        for key, child in value.items():
            child_pointer = f"{pointer}/{key}"
            yield key, child_pointer
            yield from _walk_keys(child, child_pointer)
    elif isinstance(value, list):
        for index, child in enumerate(value):
            yield from _walk_keys(child, f"{pointer}/{index}")


def _find_parent_cycles(nodes_by_id: dict[str, dict[str, Any]]) -> list[GraphIRError]:
    errors: list[GraphIRError] = []
    for start_id in nodes_by_id:
        path: list[str] = []
        seen: set[str] = set()
        current = start_id
        while current:
            if current in seen:
                cycle = " -> ".join(path + [current])
                errors.append(
                    GraphIRError("HIERARCHY_CYCLE", f"Parent hierarchy cycle: {cycle}", "/nodes")
                )
                break
            seen.add(current)
            path.append(current)
            parent = nodes_by_id.get(current, {}).get("parent_node_id")
            if not parent:
                break
            current = parent
    unique: dict[tuple[str, str], GraphIRError] = {}
    for error in errors:
        unique[(error.code, error.message)] = error
    return list(unique.values())


def validate_graph_ir(snapshot: dict[str, Any]) -> list[GraphIRError]:
    """Validate Graph IR structure and frozen Slice 1 semantic invariants.

    The function is read-only and fail-closed: every structural and semantic
    problem is returned as a stable error family rather than repaired.
    """
    errors: list[GraphIRError] = []
    validator = Draft202012Validator(_load_schema(), format_checker=FormatChecker())
    for issue in sorted(validator.iter_errors(snapshot), key=lambda item: list(item.path)):
        pointer = "/" + "/".join(str(part) for part in issue.absolute_path)
        errors.append(GraphIRError("SCHEMA_INVALID", issue.message, pointer or "/"))

    nodes = snapshot.get("nodes") if isinstance(snapshot.get("nodes"), list) else []
    edges = snapshot.get("edges") if isinstance(snapshot.get("edges"), list) else []

    node_ids: set[str] = set()
    nodes_by_id: dict[str, dict[str, Any]] = {}
    for index, node in enumerate(nodes):
        if not isinstance(node, dict):
            continue
        node_id = node.get("node_id")
        if isinstance(node_id, str):
            if node_id in node_ids:
                errors.append(GraphIRError("DUPLICATE_NODE_ID", node_id, f"/nodes/{index}/node_id"))
            node_ids.add(node_id)
            nodes_by_id[node_id] = node
        if not node.get("source_pointer"):
            errors.append(
                GraphIRError("MISSING_SOURCE_POINTER", "Source-backed node lacks source_pointer", f"/nodes/{index}")
            )

    edge_ids: set[str] = set()
    for index, edge in enumerate(edges):
        if not isinstance(edge, dict):
            continue
        edge_id = edge.get("edge_id")
        if isinstance(edge_id, str):
            if edge_id in edge_ids:
                errors.append(GraphIRError("DUPLICATE_EDGE_ID", edge_id, f"/edges/{index}/edge_id"))
            edge_ids.add(edge_id)

        source_id = edge.get("source_node_id")
        target_id = edge.get("target_node_id")
        if source_id not in node_ids or target_id not in node_ids:
            errors.append(
                GraphIRError(
                    "MISSING_EDGE_ENDPOINT",
                    f"Edge endpoint missing: {source_id} -> {target_id}",
                    f"/edges/{index}",
                )
            )

        evidence_state = edge.get("evidence_state")
        if not evidence_state:
            errors.append(
                GraphIRError("MISSING_EVIDENCE_STATE", "Edge lacks evidence_state", f"/edges/{index}")
            )
        if evidence_state in DERIVED_EVIDENCE_STATES and "confidence" not in edge:
            errors.append(
                GraphIRError(
                    "INFERRED_EDGE_WITHOUT_CONFIDENCE",
                    "Derived or inferred edge requires confidence",
                    f"/edges/{index}",
                )
            )
        if edge.get("relation_type") == "similar_to" and evidence_state not in DERIVED_EVIDENCE_STATES:
            errors.append(
                GraphIRError(
                    "ILLEGAL_RELATION_TYPE",
                    "similar_to may only be derived or inferred",
                    f"/edges/{index}/relation_type",
                )
            )

    for index, node in enumerate(nodes):
        if not isinstance(node, dict):
            continue
        parent = node.get("parent_node_id")
        if parent and parent not in node_ids:
            errors.append(
                GraphIRError("PARENT_NOT_FOUND", f"Parent node not found: {parent}", f"/nodes/{index}/parent_node_id")
            )

    errors.extend(_find_parent_cycles(nodes_by_id))

    for key, pointer in _walk_keys(snapshot):
        if key in RENDERER_ONLY_KEYS:
            errors.append(
                GraphIRError(
                    "RENDERER_STATE_IN_GRAPH_IR",
                    f"Renderer or manual view state is forbidden in Graph IR: {key}",
                    pointer,
                )
            )

    return errors
