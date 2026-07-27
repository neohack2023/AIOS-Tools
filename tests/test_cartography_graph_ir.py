from copy import deepcopy

from aios_tools.cartography import edge_id_for, node_id_for, validate_graph_ir


def make_snapshot():
    root_id = node_id_for("notion", "page", "root-page")
    child_id = node_id_for("drive", "folder", "child-folder")
    edge_id = edge_id_for("contains", root_id, child_id, "notion://root-page#children")
    return {
        "graph_ir_version": "0.1",
        "snapshot_id": "fixture-system-overview-v0.1",
        "snapshot_digest": "0" * 64,
        "created_at": "2026-07-27T00:00:00Z",
        "scope_key": "global-working-memory",
        "source_coverage": [
            {
                "adapter_id": "fixture.notion-page-tree",
                "adapter_version": "0.1",
                "source_system": "notion",
                "source_pointer": "notion://root-page",
                "source_modification_marker": "2026-07-27T00:00:00Z",
                "permission_state": "FULL",
                "coverage_state": "COMPLETE",
                "observed_objects": 2,
                "omitted_objects": 0,
                "unsupported_fields": [],
                "warnings": [],
                "errors": [],
            }
        ],
        "adapter_versions": {"fixture.notion-page-tree": "0.1"},
        "nodes": [
            {
                "node_id": root_id,
                "node_type": "authority_surface",
                "label": "Notion",
                "scope_key": "global-working-memory",
                "source_system": "notion",
                "source_object_type": "page",
                "source_object_id": "root-page",
                "source_pointer": "notion://root-page",
                "authority_role": "AUTHORITATIVE",
                "lifecycle_state": "ACTIVE",
                "verification_state": "PASSED",
                "freshness_state": "CURRENT",
                "attributes": {},
            },
            {
                "node_id": child_id,
                "node_type": "source_folder",
                "label": "Cartography package",
                "scope_key": "global-working-memory",
                "parent_node_id": root_id,
                "source_system": "drive",
                "source_object_type": "folder",
                "source_object_id": "child-folder",
                "source_pointer": "gdrive://child-folder",
                "authority_role": "DRIVE_SHADOW",
                "lifecycle_state": "CANDIDATE",
                "verification_state": "PENDING",
                "freshness_state": "CURRENT",
                "attributes": {},
            },
        ],
        "edges": [
            {
                "edge_id": edge_id,
                "relation_type": "contains",
                "source_node_id": root_id,
                "target_node_id": child_id,
                "directionality": "DIRECTED",
                "scope_key": "global-working-memory",
                "source_pointer": "notion://root-page#children",
                "authority_role": "AUTHORITATIVE",
                "evidence_state": "DIRECT_SOURCE",
                "explanation": "The source hierarchy directly contains the child.",
                "attributes": {},
            }
        ],
        "unresolved_references": [],
        "validation_summary": {"structural": "PASSED", "semantic": "PASSED", "errors": []},
    }


def test_source_identity_is_deterministic_and_label_independent():
    first = node_id_for("notion", "page", "abc")
    second = node_id_for("notion", "page", "abc")
    renamed = node_id_for("notion", "page", "abc")
    assert first == second == renamed


def test_edge_identity_changes_when_evidence_changes():
    source = node_id_for("notion", "page", "a")
    target = node_id_for("drive", "folder", "b")
    first = edge_id_for("contains", source, target, "evidence:1")
    second = edge_id_for("contains", source, target, "evidence:2")
    assert first != second


def test_valid_fixture_passes_structural_and_semantic_validation():
    assert validate_graph_ir(make_snapshot()) == []


def test_duplicate_titles_remain_distinct_source_objects():
    snapshot = make_snapshot()
    snapshot["nodes"][1]["label"] = snapshot["nodes"][0]["label"]
    assert snapshot["nodes"][0]["node_id"] != snapshot["nodes"][1]["node_id"]
    assert validate_graph_ir(snapshot) == []


def test_missing_endpoint_fails_closed():
    snapshot = make_snapshot()
    snapshot["edges"][0]["target_node_id"] = node_id_for("drive", "folder", "missing")
    codes = {error.code for error in validate_graph_ir(snapshot)}
    assert "MISSING_EDGE_ENDPOINT" in codes


def test_parent_cycle_fails_closed():
    snapshot = make_snapshot()
    snapshot["nodes"][0]["parent_node_id"] = snapshot["nodes"][1]["node_id"]
    codes = {error.code for error in validate_graph_ir(snapshot)}
    assert "HIERARCHY_CYCLE" in codes


def test_inferred_edge_requires_confidence():
    snapshot = make_snapshot()
    edge = snapshot["edges"][0]
    edge["relation_type"] = "similar_to"
    edge["evidence_state"] = "INFERRED_ANALYSIS"
    edge["edge_id"] = edge_id_for(
        "similar_to", edge["source_node_id"], edge["target_node_id"], edge["source_pointer"]
    )
    codes = {error.code for error in validate_graph_ir(snapshot)}
    assert "INFERRED_EDGE_WITHOUT_CONFIDENCE" in codes


def test_renderer_state_is_rejected_anywhere_in_graph_ir():
    snapshot = make_snapshot()
    snapshot["nodes"][0]["attributes"]["position"] = {"x": 1, "y": 2}
    codes = {error.code for error in validate_graph_ir(snapshot)}
    assert "RENDERER_STATE_IN_GRAPH_IR" in codes


def test_input_is_not_mutated():
    snapshot = make_snapshot()
    before = deepcopy(snapshot)
    validate_graph_ir(snapshot)
    assert snapshot == before
