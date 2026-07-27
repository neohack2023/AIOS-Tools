"""Deterministic, renderer-neutral scene compilation and SVG export."""
from __future__ import annotations

from html import escape
from typing import Any

from .canonical import canonical_json
from .graph_ir import validate_graph_ir

NODE_WIDTH = 240
NODE_HEIGHT = 72
GAP_X = 96
GAP_Y = 38
MARGIN = 64

_PALETTE = {
    "AUTHORITATIVE": (30, 174, 255),
    "DRIVE_SHADOW": (255, 170, 0),
    "DERIVED_VIEW": (173, 105, 255),
    "IMPLEMENTATION": (64, 214, 146),
}


def _color(role: str) -> tuple[int, int, int]:
    return _PALETTE.get(role, (120, 145, 170))


def _node_sort_key(node: dict[str, Any]) -> tuple[str, str, str]:
    return (str(node.get("node_type", "")), str(node.get("label", "")).casefold(), node["node_id"])


def compile_render_scene(
    snapshot: dict[str, Any],
    compiled_view: dict[str, Any],
    *,
    identity_resolution: dict[str, Any] | None = None,
    drift_report: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Compile stable draw primitives from validated Graph IR and governed evidence."""
    errors = validate_graph_ir(snapshot)
    if errors:
        raise ValueError("Refusing to render invalid Graph IR")

    included_node_ids = set(compiled_view.get("included_node_ids", []))
    included_edge_ids = set(compiled_view.get("included_edge_ids", []))
    nodes = sorted(
        (node for node in snapshot.get("nodes", []) if node["node_id"] in included_node_ids),
        key=_node_sort_key,
    )
    edges = sorted(
        (edge for edge in snapshot.get("edges", []) if edge["edge_id"] in included_edge_ids),
        key=lambda edge: (edge.get("relation_type", ""), edge["source_node_id"], edge["target_node_id"], edge["edge_id"]),
    )

    lanes = sorted({str(node.get("node_type", "unknown")) for node in nodes})
    lane_index = {lane: index for index, lane in enumerate(lanes)}
    lane_rows: dict[str, int] = {lane: 0 for lane in lanes}
    scene_nodes: list[dict[str, Any]] = []
    positions: dict[str, tuple[int, int]] = {}
    drift_by_source: dict[str, str] = {}
    for comparison in (drift_report or {}).get("comparisons", []):
        state = str(comparison.get("state", "UNKNOWN"))
        for key in ("notion_source_object_id", "drive_source_object_id"):
            source_id = comparison.get(key)
            if source_id:
                drift_by_source[str(source_id)] = state

    for node in nodes:
        lane = str(node.get("node_type", "unknown"))
        row = lane_rows[lane]
        lane_rows[lane] += 1
        x = MARGIN + lane_index[lane] * (NODE_WIDTH + GAP_X)
        y = MARGIN + 52 + row * (NODE_HEIGHT + GAP_Y)
        positions[node["node_id"]] = (x, y)
        rgb = _color(str(node.get("authority_role", "")))
        scene_nodes.append({
            "node_id": node["node_id"],
            "label": str(node.get("label", node["node_id"])),
            "node_type": lane,
            "authority_role": str(node.get("authority_role", "UNSPECIFIED")),
            "source_system": str(node.get("source_system", "unknown")),
            "source_object_id": str(node.get("source_object_id", "")),
            "source_pointer": str(node.get("source_pointer", "")),
            "drift_state": drift_by_source.get(str(node.get("source_object_id", "")), "NOT_COMPARED"),
            "x": x,
            "y": y,
            "width": NODE_WIDTH,
            "height": NODE_HEIGHT,
            "accent_rgb": list(rgb),
        })

    scene_edges: list[dict[str, Any]] = []
    for edge in edges:
        source = positions.get(edge["source_node_id"])
        target = positions.get(edge["target_node_id"])
        if source is None or target is None:
            raise ValueError("Compiled view contains an edge with an omitted endpoint")
        sx, sy = source
        tx, ty = target
        x1, y1 = sx + NODE_WIDTH, sy + NODE_HEIGHT // 2
        x2, y2 = tx, ty + NODE_HEIGHT // 2
        mid_x = (x1 + x2) // 2
        scene_edges.append({
            "edge_id": edge["edge_id"],
            "relation_type": str(edge.get("relation_type", "related_to")),
            "source_node_id": edge["source_node_id"],
            "target_node_id": edge["target_node_id"],
            "evidence_state": str(edge.get("evidence_state", "UNKNOWN")),
            "points": [[x1, y1], [mid_x, y1], [mid_x, y2], [x2, y2]],
        })

    max_rows = max(lane_rows.values(), default=1)
    width = max(720, MARGIN * 2 + max(1, len(lanes)) * NODE_WIDTH + max(0, len(lanes) - 1) * GAP_X)
    height = max(420, MARGIN * 2 + 52 + max_rows * NODE_HEIGHT + max(0, max_rows - 1) * GAP_Y)
    resolved = sorted((identity_resolution or {}).get("resolved", []), key=lambda item: str(item.get("entity_id", "")))
    unresolved = sorted((identity_resolution or {}).get("unresolved", []), key=canonical_json)
    scene = {
        "renderer_contract": "aios.cartography.scene.v0.1",
        "source_snapshot_id": snapshot["snapshot_id"],
        "source_snapshot_digest": snapshot["snapshot_digest"],
        "view_id": compiled_view["view_id"],
        "identity_summary": {"resolved_count": len(resolved), "unresolved_count": len(unresolved), "resolved": resolved, "unresolved": unresolved},
        "drift_summary": {
            "drift_count": int((drift_report or {}).get("drift_count", 0)),
            "comparison_count": len((drift_report or {}).get("comparisons", [])),
        },
        "width": width,
        "height": height,
        "lanes": [{"name": lane, "x": MARGIN + lane_index[lane] * (NODE_WIDTH + GAP_X)} for lane in lanes],
        "nodes": scene_nodes,
        "edges": scene_edges,
    }
    scene["scene_digest_material"] = canonical_json(scene)
    return scene


def render_svg(scene: dict[str, Any], *, title: str = "AIOS Cartography") -> str:
    """Render a deterministic standalone SVG document from a compiled scene."""
    width = int(scene["width"])
    height = int(scene["height"])
    subtitle = f'identity {scene.get("identity_summary", {}).get("resolved_count", 0)} · drift {scene.get("drift_summary", {}).get("drift_count", 0)}'
    parts = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}" role="img">',
        f'<title>{escape(title)}</title>',
        '<defs><marker id="arrow" markerWidth="8" markerHeight="8" refX="7" refY="4" orient="auto"><path d="M0,0 L8,4 L0,8 Z" fill="#657b91"/></marker></defs>',
        '<rect width="100%" height="100%" fill="#071018"/>',
        f'<text x="{MARGIN}" y="30" fill="#e8f2f8" font-family="ui-monospace,monospace" font-size="22" font-weight="700">{escape(title)}</text>',
        f'<text x="{MARGIN}" y="48" fill="#7f9aad" font-family="ui-monospace,monospace" font-size="10">{escape(subtitle)}</text>',
    ]
    for lane in scene.get("lanes", []):
        parts.append(f'<text x="{lane["x"]}" y="{MARGIN + 24}" fill="#6f879b" font-family="ui-monospace,monospace" font-size="12">{escape(lane["name"])}</text>')
    for edge in scene.get("edges", []):
        points = " ".join(f'{int(x)},{int(y)}' for x, y in edge["points"])
        parts.append(f'<polyline points="{points}" fill="none" stroke="#657b91" stroke-width="2" marker-end="url(#arrow)" data-edge-id="{escape(edge["edge_id"])}"><title>{escape(edge["relation_type"])}</title></polyline>')
    for node in scene.get("nodes", []):
        r, g, b = node["accent_rgb"]
        accent = f'rgb({r},{g},{b})'
        x, y, w, h = int(node["x"]), int(node["y"]), int(node["width"]), int(node["height"])
        label = escape(node["label"])
        meta = escape(f'{node["source_system"]} · {node["authority_role"]}')
        pointer = escape(node["source_pointer"])
        parts.extend([
            f'<g data-node-id="{escape(node["node_id"])}" data-drift-state="{escape(node["drift_state"])}">',
            f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="12" fill="#0d1a25" stroke="{accent}" stroke-width="2"><title>{pointer}</title></rect>',
            f'<rect x="{x}" y="{y}" width="6" height="{h}" rx="3" fill="{accent}"/>',
            f'<text x="{x + 18}" y="{y + 30}" fill="#edf6fb" font-family="ui-sans-serif,system-ui" font-size="14" font-weight="650">{label[:34]}</text>',
            f'<text x="{x + 18}" y="{y + 52}" fill="#91a8ba" font-family="ui-monospace,monospace" font-size="10">{meta[:48]}</text>',
            '</g>',
        ])
    parts.append('</svg>')
    return "\n".join(parts) + "\n"
