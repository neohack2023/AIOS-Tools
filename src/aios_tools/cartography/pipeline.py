"""Source-backed Graph IR assembly and View Compiler proof."""

from __future__ import annotations

from typing import Any

from .canonical import snapshot_digest
from .drive_read_adapter import DriveReadResult
from .graph_ir import validate_graph_ir
from .notion_read_adapter import NotionReadResult
from .views import compile_view


def _build_snapshot(
    *,
    nodes: list[dict[str, Any]],
    edges: list[dict[str, Any]],
    unresolved_references: list[dict[str, Any]],
    observed_objects: int,
    scope_key: str,
    snapshot_id: str,
    source_pointer: str,
    source_modification_marker: str,
    created_at: str,
    adapter_id: str,
    adapter_version: str,
    source_system: str,
) -> dict[str, Any]:
    snapshot: dict[str, Any] = {
        "graph_ir_version": "0.1",
        "snapshot_id": snapshot_id,
        "snapshot_digest": "0" * 64,
        "created_at": created_at,
        "scope_key": scope_key,
        "source_coverage": [{
            "adapter_id": adapter_id,
            "adapter_version": adapter_version,
            "source_system": source_system,
            "source_pointer": source_pointer,
            "source_modification_marker": source_modification_marker,
            "permission_state": "FULL",
            "coverage_state": "COMPLETE" if not unresolved_references else "PARTIAL",
            "observed_objects": observed_objects,
            "omitted_objects": 0,
            "unsupported_fields": [],
            "warnings": [],
            "errors": [],
        }],
        "adapter_versions": {adapter_id: adapter_version},
        "nodes": nodes,
        "edges": edges,
        "unresolved_references": unresolved_references,
        "validation_summary": {"structural": "PASSED", "semantic": "PASSED", "errors": []},
    }
    errors = validate_graph_ir(snapshot)
    if errors:
        raise ValueError("Graph IR validation failed: " + "; ".join(error.code for error in errors))
    snapshot["snapshot_digest"] = snapshot_digest(snapshot)
    return snapshot


def build_notion_snapshot(
    result: NotionReadResult,
    *,
    scope_key: str,
    snapshot_id: str,
    source_pointer: str,
    source_modification_marker: str,
    created_at: str,
) -> dict[str, Any]:
    """Build and validate a deterministic Graph IR snapshot from a Notion read result."""
    return _build_snapshot(
        nodes=list(result.nodes),
        edges=list(result.edges),
        unresolved_references=list(result.unresolved_references),
        observed_objects=len(result.records),
        scope_key=scope_key,
        snapshot_id=snapshot_id,
        source_pointer=source_pointer,
        source_modification_marker=source_modification_marker,
        created_at=created_at,
        adapter_id="notion.page_chain.read_only",
        adapter_version="0.1.0",
        source_system="notion",
    )


def build_drive_snapshot(
    result: DriveReadResult,
    *,
    scope_key: str,
    snapshot_id: str,
    source_pointer: str,
    source_modification_marker: str,
    created_at: str,
) -> dict[str, Any]:
    """Build and validate a deterministic Graph IR snapshot from a Drive read result."""
    return _build_snapshot(
        nodes=list(result.nodes),
        edges=list(result.edges),
        unresolved_references=list(result.unresolved_references),
        observed_objects=len(result.records),
        scope_key=scope_key,
        snapshot_id=snapshot_id,
        source_pointer=source_pointer,
        source_modification_marker=source_modification_marker,
        created_at=created_at,
        adapter_id="drive.ancestor_chain.read_only",
        adapter_version="0.1.0",
        source_system="google_drive",
    )


def compile_source_backed_view(snapshot: dict[str, Any], view_spec: dict[str, Any]) -> dict[str, Any]:
    """Compile a view only after structural and semantic validation passes."""
    errors = validate_graph_ir(snapshot)
    if errors:
        raise ValueError("Refusing to compile invalid Graph IR")
    compiled = compile_view(snapshot, view_spec)
    compiled["source_snapshot_id"] = snapshot["snapshot_id"]
    compiled["source_snapshot_digest"] = snapshot["snapshot_digest"]
    compiled["source_coverage"] = snapshot["source_coverage"]
    return compiled
