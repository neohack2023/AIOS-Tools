"""Deterministic drift comparison for exact cross-source identities."""

from __future__ import annotations

from typing import Any


def compare_cross_source_drift(
    notion_snapshot: dict[str, Any],
    drive_snapshot: dict[str, Any],
    resolution: dict[str, Any],
) -> dict[str, Any]:
    """Compare resolved source pairs without treating Drive as authority."""
    notion_nodes = {node["node_id"]: node for node in notion_snapshot.get("nodes", [])}
    drive_nodes = {node["node_id"]: node for node in drive_snapshot.get("nodes", [])}
    comparisons: list[dict[str, Any]] = []

    for item in sorted(resolution.get("resolved", []), key=lambda value: value["entity_id"]):
        notion_node = notion_nodes[item["notion_node_id"]]
        drive_node = drive_nodes[item["drive_node_id"]]
        differences: list[dict[str, Any]] = []
        if notion_node.get("label") != drive_node.get("label"):
            differences.append({
                "field": "label",
                "notion": notion_node.get("label"),
                "drive": drive_node.get("label"),
                "classification": "DISPLAY_DRIFT",
            })
        if notion_node.get("lifecycle_state") != drive_node.get("lifecycle_state"):
            differences.append({
                "field": "lifecycle_state",
                "notion": notion_node.get("lifecycle_state"),
                "drive": drive_node.get("lifecycle_state"),
                "classification": "STATE_DRIFT",
            })
        comparisons.append({
            "entity_id": item["entity_id"],
            "binding_key": item["binding_key"],
            "notion_node_id": item["notion_node_id"],
            "drive_node_id": item["drive_node_id"],
            "authority": "NOTION",
            "shadow": "GOOGLE_DRIVE",
            "state": "ALIGNED" if not differences else "DRIFT_DETECTED",
            "differences": differences,
        })

    for item in sorted(resolution.get("unresolved", []), key=lambda value: value["binding_key"]):
        comparisons.append({
            "binding_key": item["binding_key"],
            "state": "UNRESOLVED_BINDING",
            "missing_sources": item["missing_sources"],
            "differences": [],
        })

    return {
        "drift_version": "0.1",
        "notion_snapshot_id": notion_snapshot["snapshot_id"],
        "notion_snapshot_digest": notion_snapshot["snapshot_digest"],
        "drive_snapshot_id": drive_snapshot["snapshot_id"],
        "drive_snapshot_digest": drive_snapshot["snapshot_digest"],
        "comparison_count": len(comparisons),
        "drift_count": sum(item["state"] != "ALIGNED" for item in comparisons),
        "comparisons": comparisons,
    }
