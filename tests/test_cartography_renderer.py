from copy import deepcopy

import pytest

from aios_tools.cartography import (
    compile_render_scene,
    edge_id_for,
    node_id_for,
    render_png,
    render_svg,
    render_webgpu_html,
)


def snapshot():
    notion = node_id_for("notion", "page", "cartography-contract")
    drive = node_id_for("google_drive", "file", "cartography-shadow")
    edge = edge_id_for("contains", notion, drive, "registered-binding")
    return {
        "graph_ir_version": "0.1",
        "snapshot_id": "renderer-source-proof-v0.1",
        "snapshot_digest": "a" * 64,
        "created_at": "2026-07-27T13:04:06Z",
        "scope_key": "global-working-memory",
        "source_coverage": [{
            "adapter_id": "source-backed-proof",
            "adapter_version": "0.1.0",
            "source_system": "notion+google_drive",
            "source_pointer": "registered-binding",
            "source_modification_marker": "2026-07-27T13:04:06Z",
            "permission_state": "FULL",
            "coverage_state": "COMPLETE",
            "observed_objects": 2,
            "omitted_objects": 0,
            "unsupported_fields": [],
            "warnings": [],
            "errors": [],
        }],
        "adapter_versions": {"notion.page_chain.read_only": "0.1.0", "drive.ancestor_chain.read_only": "0.1.0"},
        "nodes": [
            {
                "node_id": notion,
                "node_type": "knowledge_object",
                "label": "AIOS Cartography Contract",
                "scope_key": "global-working-memory",
                "source_system": "notion",
                "source_object_type": "page",
                "source_object_id": "cartography-contract",
                "source_pointer": "https://notion.so/cartography-contract",
                "authority_role": "AUTHORITATIVE",
                "lifecycle_state": "ACTIVE",
                "verification_state": "PASSED",
                "freshness_state": "CURRENT",
                "attributes": {},
            },
            {
                "node_id": drive,
                "node_type": "source_file",
                "label": "Cartography Contract drive_shadow",
                "scope_key": "global-working-memory",
                "parent_node_id": notion,
                "source_system": "google_drive",
                "source_object_type": "file",
                "source_object_id": "cartography-shadow",
                "source_pointer": "https://drive.google.com/cartography-shadow",
                "authority_role": "DRIVE_SHADOW",
                "lifecycle_state": "ACTIVE",
                "verification_state": "PASSED",
                "freshness_state": "CURRENT",
                "attributes": {},
            },
        ],
        "edges": [{
            "edge_id": edge,
            "relation_type": "contains",
            "source_node_id": notion,
            "target_node_id": drive,
            "directionality": "DIRECTED",
            "scope_key": "global-working-memory",
            "source_pointer": "registered-binding",
            "authority_role": "DERIVED_VIEW",
            "evidence_state": "REGISTERED_BINDING",
            "explanation": "Registered authority to shadow binding.",
            "attributes": {},
        }],
        "unresolved_references": [],
        "validation_summary": {"structural": "PASSED", "semantic": "PASSED", "errors": []},
    }


def view(data):
    return {
        "view_id": "source-backed-render-proof-v0.1",
        "included_node_ids": sorted(node["node_id"] for node in data["nodes"]),
        "included_edge_ids": sorted(edge["edge_id"] for edge in data["edges"]),
        "excluded_node_count": 0,
        "excluded_edge_count": 0,
        "source_snapshot_id": data["snapshot_id"],
        "source_snapshot_digest": data["snapshot_digest"],
        "source_coverage": data["source_coverage"],
    }


def test_scene_compilation_is_deterministic_and_input_order_independent():
    data = snapshot()
    first = compile_render_scene(data, view(data))
    reordered = deepcopy(data)
    reordered["nodes"].reverse()
    second = compile_render_scene(reordered, view(reordered))
    assert first == second
    assert first["source_snapshot_digest"] == data["snapshot_digest"]
    assert all("x" in node and "y" in node for node in first["nodes"])


def test_svg_is_stable_searchable_and_source_backed():
    data = snapshot()
    scene = compile_render_scene(data, view(data))
    first = render_svg(scene)
    second = render_svg(scene)
    assert first == second
    assert "AIOS Cartography Contract" in first
    assert data["nodes"][0]["node_id"] in first
    assert "<script" not in first


def test_png_has_valid_signature_and_deterministic_bytes():
    data = snapshot()
    scene = compile_render_scene(data, view(data))
    first = render_png(scene)
    second = render_png(scene)
    assert first == second
    assert first.startswith(b"\x89PNG\r\n\x1a\n")
    assert b"snapshot=" + data["snapshot_digest"].encode() in first


def test_webgpu_viewer_is_self_contained_and_read_only():
    data = snapshot()
    html = render_webgpu_html(compile_render_scene(data, view(data)))
    assert "navigator.gpu" in html
    assert "Export SVG" in html
    assert "Export PNG" in html
    assert "fetch(" not in html
    assert "XMLHttpRequest" not in html
    assert "update_page" not in html
    assert data["snapshot_digest"] in html


def test_renderer_refuses_invalid_graph_ir():
    data = snapshot()
    data["nodes"][0]["attributes"]["position"] = {"x": 1, "y": 2}
    with pytest.raises(ValueError, match="invalid Graph IR"):
        compile_render_scene(data, view(data))


def test_renderer_refuses_edge_with_omitted_endpoint():
    data = snapshot()
    compiled = view(data)
    compiled["included_node_ids"] = [data["nodes"][0]["node_id"]]
    with pytest.raises(ValueError, match="omitted endpoint"):
        compile_render_scene(data, compiled)
