"""Source-backed Graph IR assembly and View Compiler proof."""

from __future__ import annotations

from typing import Any

from .canonical import snapshot_digest
from .graph_ir import validate_graph_ir
from .notion_read_adapter import NotionReadResult
from .views import compile_view


def build_notion_snapshot(
    result: NotionReadResult,
    *,
    scope_key: str,
    snapshot_id: str,
    source_pointer: str,
    source_modification_marker: str,
    created_at: str,
) -> dict[str, Any]:
    """Build and validate a deterministic Graph IR snapshot from a real read result."""
    snapshot: dict[str, Any] = {
        "graph_ir_version": "0.1",
        "snapshot_id": snapshot_id,
        "snapshot_digest": "0" * 64,
        "created_at": created_at,
        "scope_key": scope_key,
        "source_coverage": [{
            "adapter_id": "notion.page_chain.read_only",
            "adapter_version": "0.1.0",
            "source_system": "notion",
            "source_pointer": source_pointer,
            "source_modification_marker": source_modification_marker,
            "permission_state": "FULL",
            "coverage_state": "COMPLETE" if not result.unresolved_references else "PARTIAL",
            "observed_objects": len(result.records),
            "omitted_objects": 0,
            "unsupported_fields": [],
            "warnings": [],
            "errors": [],
        }],
        "adapter_versions": {"notion.page_chain.read_only": "0.1.0"},
        "nodes": list(result.nodes),
        "edges": list(result.edges),
        "unresolved_references": list(result.unresolved_references),
        "validation_summary": {"structural": "PASSED", "semantic": "PASSED", "errors": []},
    }
    errors = validate_graph_ir(snapshot)
    if errors:
        raise ValueError("Graph IR validation failed: " + "; ".join(error.code for error in errors))
    snapshot["snapshot_digest"] = snapshot_digest(snapshot)
    return snapshot


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
