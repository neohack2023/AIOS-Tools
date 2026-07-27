import json
from copy import deepcopy
from pathlib import Path

from aios_tools.cartography import (
    DriveAncestorChainAdapter,
    ExactIdentityBinding,
    NotionPageChainAdapter,
    build_drive_snapshot,
    build_notion_snapshot,
    compare_cross_source_drift,
    compile_render_scene,
    render_svg,
    render_webgpu_html,
    resolve_exact_identities,
)

ROOT = Path(__file__).resolve().parents[1]
NOTION = ROOT / "fixtures/cartography/source-backed/notion-cartography-chain.2026-07-27.json"
DRIVE = ROOT / "fixtures/cartography/source-backed/drive-cartography-chain.2026-07-27.json"


class NotionClient:
    def __init__(self, rows):
        self.rows = {row["id"]: deepcopy(row) for row in rows}

    def fetch_page(self, page_id):
        return deepcopy(self.rows[page_id])


class DriveClient:
    def __init__(self, rows):
        self.rows = {row["id"]: deepcopy(row) for row in rows}

    def get_metadata(self, file_id):
        return deepcopy(self.rows[file_id])


def load(path):
    return json.loads(path.read_text(encoding="utf-8"))


def test_live_adapter_identity_drift_view_and_renderer_chain():
    notion_evidence, drive_evidence = load(NOTION), load(DRIVE)
    notion_result = NotionPageChainAdapter(NotionClient(notion_evidence["records"])).read(
        notion_evidence["root_page_id"], notion_evidence["scope_key"]
    )
    drive_result = DriveAncestorChainAdapter(DriveClient(drive_evidence["records"])).read(
        drive_evidence["root_file_id"], drive_evidence["scope_key"]
    )
    notion_snapshot = build_notion_snapshot(
        notion_result,
        scope_key=notion_evidence["scope_key"],
        snapshot_id=notion_evidence["evidence_id"],
        source_pointer=notion_evidence["provenance"]["source_pointer"],
        source_modification_marker=notion_evidence["observed_at"],
        created_at=notion_evidence["observed_at"],
    )
    drive_snapshot = build_drive_snapshot(
        drive_result,
        scope_key=drive_evidence["scope_key"],
        snapshot_id=drive_evidence["evidence_id"],
        source_pointer=drive_evidence["provenance"]["source_pointer"],
        source_modification_marker=drive_evidence["observed_at"],
        created_at=drive_evidence["observed_at"],
    )
    bindings = [ExactIdentityBinding(**item) for item in drive_evidence["exact_bindings"]]
    identity = resolve_exact_identities(notion_snapshot, drive_snapshot, bindings)
    drift = compare_cross_source_drift(notion_snapshot, drive_snapshot, identity)
    compiled_view = {
        "view_id": "drive-authority-shadow-proof-v0.1",
        "included_node_ids": sorted(node["node_id"] for node in drive_snapshot["nodes"]),
        "included_edge_ids": sorted(edge["edge_id"] for edge in drive_snapshot["edges"]),
        "excluded_node_count": 0,
        "excluded_edge_count": 0,
    }
    scene = compile_render_scene(
        drive_snapshot,
        compiled_view,
        identity_resolution=identity,
        drift_report=drift,
    )
    assert scene["identity_summary"]["resolved_count"] == 1
    assert scene["drift_summary"]["drift_count"] == 1
    assert scene["source_snapshot_digest"] == drive_snapshot["snapshot_digest"]
    assert "identity 1 · drift 1" in render_svg(scene)
    html = render_webgpu_html(scene)
    assert "WebGPU surface + deterministic overlay" in html
    assert "fetch(" not in html
