import json
from copy import deepcopy
from pathlib import Path

from aios_tools.cartography import (
    DriveAncestorChainAdapter,
    build_drive_snapshot,
    compile_mindmap_scene,
    render_mindmap_svg,
    render_mindmap_webgpu_html,
)

ROOT = Path(__file__).resolve().parents[1]
EVIDENCE = ROOT / "fixtures/cartography/source-backed/drive-cartography-chain.2026-07-27.json"


class Client:
    def __init__(self, records):
        self.records = {row["id"]: deepcopy(row) for row in records}

    def get_metadata(self, file_id):
        return deepcopy(self.records[file_id])


def proof():
    evidence = json.loads(EVIDENCE.read_text(encoding="utf-8"))
    result = DriveAncestorChainAdapter(Client(evidence["records"])).read(evidence["root_file_id"], evidence["scope_key"])
    snapshot = build_drive_snapshot(
        result,
        scope_key=evidence["scope_key"],
        snapshot_id=evidence["evidence_id"],
        source_pointer=evidence["provenance"]["source_pointer"],
        source_modification_marker=evidence["observed_at"],
        created_at=evidence["observed_at"],
    )
    view = {
        "view_id": "aios-system-mind-map-v0.1",
        "included_node_ids": sorted(node["node_id"] for node in snapshot["nodes"]),
        "included_edge_ids": sorted(edge["edge_id"] for edge in snapshot["edges"]),
    }
    root_source_id = evidence["records"][-1]["id"]
    root_node_id = next(node["node_id"] for node in snapshot["nodes"] if node["source_object_id"] == root_source_id)
    return compile_mindmap_scene(snapshot, view, root_node_id=root_node_id)


def test_mindmap_is_deterministic_and_central_rooted():
    first, second = proof(), proof()
    assert first == second
    assert first["layout"] == "radial-semantic"
    root = next(node for node in first["nodes"] if node["is_root"])
    assert root["node_id"] == first["root_node_id"]
    assert root["depth"] == 0
    assert all("path" in edge and len(edge["path"]) == 4 for edge in first["edges"])


def test_mindmap_wraps_labels_and_has_mobile_fit_contract():
    scene = proof()
    assert all(1 <= len(node["label_lines"]) <= 3 for node in scene["nodes"])
    assert scene["mobile_fit"]["fit_mode"] == "contain"
    assert scene["mobile_fit"]["min_zoom"] > 0


def test_mindmap_exports_svg_and_interactive_depth_controls():
    scene = proof()
    svg = render_mindmap_svg(scene)
    html = render_mindmap_webgpu_html(scene)
    assert "bezier" not in svg.lower()
    assert " C" in svg
    assert "AIOS System Mind Map" in svg
    assert "Depth 4" in html
    assert "label_lines" in html
    assert "fetch(" not in html


def test_root_must_be_in_compiled_view():
    scene = proof()
    assert scene["root_node_id"] in {node["node_id"] for node in scene["nodes"]}
