from copy import deepcopy

import pytest

from aios_tools.cartography.canonical import canonical_json, snapshot_digest
from aios_tools.cartography.fixtures import (
    adapt_capability_registry,
    adapt_drive_tree,
    adapt_notion_page_tree,
    adapt_scope_registry,
)
from aios_tools.cartography.graph_ir import edge_id_for, node_id_for
from aios_tools.cartography.views import SYSTEM_OVERVIEW_VIEW, WORKFLOW_CONTROL_PLANE_VIEW, compile_view


def make_snapshot():
    root = node_id_for("notion", "page", "root")
    scope = node_id_for("project_scope_registry", "scope_row", "global-working-memory")
    edge = edge_id_for("contains", root, scope, "notion://root#scope")
    return {
        "graph_ir_version": "0.1",
        "snapshot_id": "slice2-fixture",
        "snapshot_digest": "0" * 64,
        "created_at": "2026-07-27T00:00:00Z",
        "scope_key": "global-working-memory",
        "source_coverage": [{
            "adapter_id": "fixture.slice2",
            "adapter_version": "0.1",
            "source_system": "mixed_fixture",
            "source_pointer": "fixture://slice2",
            "source_modification_marker": "v1",
            "permission_state": "FULL",
            "coverage_state": "COMPLETE",
            "observed_objects": 2,
            "omitted_objects": 0,
            "unsupported_fields": [],
            "warnings": [],
            "errors": [],
        }],
        "adapter_versions": {"fixture.slice2": "0.1"},
        "nodes": [
            {
                "node_id": root,
                "node_type": "authority_surface",
                "label": "Notion",
                "scope_key": "global-working-memory",
                "source_system": "notion",
                "source_object_type": "page",
                "source_object_id": "root",
                "source_pointer": "notion://root",
                "authority_role": "AUTHORITATIVE",
                "lifecycle_state": "ACTIVE",
                "verification_state": "PASSED",
                "freshness_state": "CURRENT",
                "attributes": {},
            },
            {
                "node_id": scope,
                "node_type": "scope",
                "label": "Global Working Memory",
                "scope_key": "global-working-memory",
                "parent_node_id": root,
                "source_system": "project_scope_registry",
                "source_object_type": "scope_row",
                "source_object_id": "global-working-memory",
                "source_pointer": "registry://scope/global-working-memory",
                "authority_role": "AUTHORITATIVE",
                "lifecycle_state": "ACTIVE",
                "verification_state": "PASSED",
                "freshness_state": "CURRENT",
                "attributes": {},
            },
        ],
        "edges": [{
            "edge_id": edge,
            "relation_type": "contains",
            "source_node_id": root,
            "target_node_id": scope,
            "directionality": "DIRECTED",
            "scope_key": "global-working-memory",
            "source_pointer": "notion://root#scope",
            "authority_role": "AUTHORITATIVE",
            "evidence_state": "DIRECT_SOURCE",
            "explanation": "Fixture containment",
            "attributes": {},
        }],
        "unresolved_references": [],
        "validation_summary": {"structural": "PASSED", "semantic": "PASSED", "errors": []},
    }


def test_digest_is_order_independent_and_input_is_unchanged():
    first = make_snapshot()
    second = deepcopy(first)
    second["nodes"].reverse()
    second["edges"].reverse()
    before = deepcopy(second)
    assert snapshot_digest(first) == snapshot_digest(second)
    assert canonical_json(first) == canonical_json(second)
    assert second == before


def test_digest_rejects_negative_zero():
    snapshot = make_snapshot()
    snapshot["nodes"][0]["attributes"]["bad"] = -0.0
    with pytest.raises(ValueError, match="UNSUPPORTED_CANONICAL_VALUE"):
        snapshot_digest(snapshot)


def test_notion_and_drive_adapters_are_deterministic_and_preserve_unresolved():
    notion_rows = [
        {"id": "child", "title": "Child", "url": "notion://child", "parent_id": "missing"},
        {"id": "root", "title": "Root", "url": "notion://root"},
    ]
    first = adapt_notion_page_tree(notion_rows, "global-working-memory")
    second = adapt_notion_page_tree(list(reversed(notion_rows)), "global-working-memory")
    assert first == second
    assert first[2][0]["reason"] == "parent_not_in_fixture"

    drive_rows = [
        {"id": "f2", "name": "Same", "url": "gdrive://f2", "type": "file", "parent_id": "f1"},
        {"id": "f1", "name": "Same", "url": "gdrive://f1", "type": "folder"},
    ]
    nodes, edges, unresolved = adapt_drive_tree(drive_rows, "global-working-memory")
    assert len({node["node_id"] for node in nodes}) == 2
    assert len(edges) == 1
    assert unresolved == []


def test_registry_adapters_bind_exact_scopes_and_fail_closed():
    scope_rows = [
        {"scope_key": "global-working-memory", "label": "Global", "source_pointer": "registry://global"},
        {"scope_key": "udio-algorithms", "label": "Udio", "source_pointer": "registry://udio", "parent_scope": "global-working-memory", "aliases": ["Ne0 Hack"]},
    ]
    scope_nodes, scope_edges, unresolved = adapt_scope_registry(scope_rows)
    known = {node["scope_key"]: node["node_id"] for node in scope_nodes}
    assert len(scope_edges) == 1
    assert unresolved == []

    capabilities = [
        {"capability_id": "cartography", "label": "Cartography", "scope_key": "global-working-memory", "source_pointer": "registry://cap/cartography"},
        {"capability_id": "orphan", "label": "Orphan", "scope_key": "missing-scope", "source_pointer": "registry://cap/orphan"},
    ]
    _, capability_edges, capability_unresolved = adapt_capability_registry(capabilities, known)
    assert len(capability_edges) == 1
    assert capability_unresolved[0]["reason"] == "scope_not_registered"


def test_both_view_specs_compile_stably_without_rendering():
    snapshot = make_snapshot()
    first = compile_view(snapshot, SYSTEM_OVERVIEW_VIEW)
    second = compile_view(deepcopy(snapshot), SYSTEM_OVERVIEW_VIEW)
    workflow = compile_view(snapshot, WORKFLOW_CONTROL_PLANE_VIEW)
    assert first == second
    assert "layout" not in first and "coordinates" not in first
    assert workflow["view_id"] == "workflow-control-plane-v0.1"
