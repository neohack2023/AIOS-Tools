"""Deterministic central-root semantic mind-map layout for Cartography."""
from __future__ import annotations

import json
import math
from collections import defaultdict, deque
from typing import Any

from .graph_ir import validate_graph_ir


def _stable(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, allow_nan=False, sort_keys=True, separators=(",", ":"))


def _wrap(label: str, width: int = 28, lines: int = 3) -> list[str]:
    words = label.replace("_", " ").split()
    out: list[str] = []
    current = ""
    for word in words:
        candidate = word if not current else f"{current} {word}"
        if len(candidate) <= width:
            current = candidate
        else:
            if current:
                out.append(current)
            current = word
            if len(out) == lines - 1:
                break
    if current and len(out) < lines:
        out.append(current)
    consumed = " ".join(out)
    if len(consumed) < len(" ".join(words)) and out:
        out[-1] = out[-1][: max(1, width - 1)].rstrip() + "…"
    return out or [label[:width]]


def compile_mindmap_scene(
    snapshot: dict[str, Any],
    compiled_view: dict[str, Any],
    *,
    root_node_id: str,
    title: str = "AIOS System Mind Map",
    max_depth: int = 4,
    identity_resolution: dict[str, Any] | None = None,
    drift_report: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Compile a stable radial mind map without changing Graph IR knowledge."""
    if validate_graph_ir(snapshot):
        raise ValueError("Refusing to render invalid Graph IR")
    included = set(compiled_view.get("included_node_ids", []))
    included_edges = set(compiled_view.get("included_edge_ids", []))
    nodes = {n["node_id"]: n for n in snapshot.get("nodes", []) if n["node_id"] in included}
    if root_node_id not in nodes:
        raise ValueError("Mind-map root is not included in the compiled view")

    edges = [e for e in snapshot.get("edges", []) if e["edge_id"] in included_edges and e["source_node_id"] in nodes and e["target_node_id"] in nodes]
    adjacency: dict[str, list[str]] = defaultdict(list)
    edge_by_pair: dict[tuple[str, str], dict[str, Any]] = {}
    for edge in sorted(edges, key=lambda e: (e.get("relation_type", ""), e["edge_id"])):
        a, b = edge["source_node_id"], edge["target_node_id"]
        adjacency[a].append(b); adjacency[b].append(a)
        edge_by_pair[(a, b)] = edge; edge_by_pair[(b, a)] = edge
    for values in adjacency.values():
        values.sort(key=lambda nid: (str(nodes[nid].get("label", "")).casefold(), nid))

    parent: dict[str, str | None] = {root_node_id: None}
    depth = {root_node_id: 0}
    order: list[str] = []
    queue = deque([root_node_id])
    while queue:
        current = queue.popleft(); order.append(current)
        if depth[current] >= max_depth:
            continue
        for child in adjacency.get(current, []):
            if child in parent:
                continue
            parent[child] = current; depth[child] = depth[current] + 1; queue.append(child)

    children: dict[str, list[str]] = defaultdict(list)
    for nid, pid in parent.items():
        if pid is not None:
            children[pid].append(nid)
    for values in children.values():
        values.sort(key=lambda nid: (str(nodes[nid].get("label", "")).casefold(), nid))

    leaves: dict[str, int] = {}
    def leaf_count(nid: str) -> int:
        if nid in leaves: return leaves[nid]
        leaves[nid] = max(1, sum(leaf_count(c) for c in children.get(nid, [])))
        return leaves[nid]
    leaf_count(root_node_id)

    width = 1600; height = 1000; cx = width // 2; cy = height // 2 + 20
    ring_step = 190; positions: dict[str, tuple[float, float]] = {root_node_id: (cx, cy)}
    def place(nid: str, start: float, span: float) -> None:
        kids = children.get(nid, [])
        cursor = start
        total = sum(leaf_count(k) for k in kids) or 1
        for kid in kids:
            child_span = span * leaf_count(kid) / total
            angle = cursor + child_span / 2
            radius = depth[kid] * ring_step
            positions[kid] = (cx + math.cos(angle) * radius, cy + math.sin(angle) * radius)
            place(kid, cursor, child_span)
            cursor += child_span
    place(root_node_id, -math.pi, math.tau)

    palette = {"AUTHORITATIVE":[30,174,255],"DRIVE_SHADOW":[255,170,0],"IMPLEMENTATION":[64,214,146],"DERIVED_VIEW":[173,105,255]}
    scene_nodes = []
    for nid in order:
        node = nodes[nid]; x, y = positions[nid]
        root = nid == root_node_id
        w, h = (260, 108) if root else (220, 86)
        scene_nodes.append({
            "node_id": nid, "label": str(node.get("label", nid)), "label_lines": _wrap(str(node.get("label", nid)), 30 if root else 25),
            "node_type": str(node.get("node_type", "unknown")), "authority_role": str(node.get("authority_role", "UNSPECIFIED")),
            "source_system": str(node.get("source_system", "unknown")), "source_pointer": str(node.get("source_pointer", "")),
            "x": round(x - w/2, 3), "y": round(y - h/2, 3), "width": w, "height": h,
            "depth": depth[nid], "parent_node_id": parent[nid], "collapsible": bool(children.get(nid)),
            "accent_rgb": palette.get(str(node.get("authority_role", "")), [120,145,170]), "is_root": root,
        })

    relation_styles = {
        "contains": {"stroke":"#4f7389","dash":[],"width":3},
        "mirrored_by": {"stroke":"#ad69ff","dash":[10,7],"width":4},
        "evidenced_by": {"stroke":"#40d692","dash":[3,6],"width":3},
        "implemented_by": {"stroke":"#40d692","dash":[],"width":3},
        "belongs_to_scope": {"stroke":"#1eaeff","dash":[],"width":3},
    }
    scene_edges = []
    for nid, pid in sorted(parent.items()):
        if pid is None: continue
        edge = edge_by_pair[(pid, nid)]; sx, sy = positions[pid]; tx, ty = positions[nid]
        c1x = sx + (tx-sx)*0.38; c1y = sy + (ty-sy)*0.18; c2x = sx + (tx-sx)*0.68; c2y = sy + (ty-sy)*0.82
        relation = str(edge.get("relation_type", "related_to")); style = relation_styles.get(relation, {"stroke":"#657b91","dash":[],"width":2})
        scene_edges.append({"edge_id":edge["edge_id"],"relation_type":relation,"source_node_id":pid,"target_node_id":nid,
                            "path":[[round(sx,3),round(sy,3)],[round(c1x,3),round(c1y,3)],[round(c2x,3),round(c2y,3)],[round(tx,3),round(ty,3)]],"style":style})

    resolved = sorted((identity_resolution or {}).get("resolved", []), key=lambda item: str(item.get("entity_id", "")))
    scene = {"renderer_contract":"aios.cartography.mindmap.v0.1","layout":"radial-semantic","title":title,
             "source_snapshot_id":snapshot["snapshot_id"],"source_snapshot_digest":snapshot["snapshot_digest"],"view_id":compiled_view["view_id"],
             "root_node_id":root_node_id,"max_depth":max_depth,"width":width,"height":height,"nodes":scene_nodes,"edges":scene_edges,
             "identity_summary":{"resolved_count":len(resolved)},"drift_summary":{"drift_count":int((drift_report or {}).get("drift_count",0))},
             "mobile_fit":{"padding":24,"min_zoom":0.18,"max_zoom":5.0,"fit_mode":"contain"}}
    scene["scene_digest_material"] = _stable(scene)
    return scene
