import json
from copy import deepcopy
from pathlib import Path

import pytest

from aios_tools.cartography import (
    NOTION_AUTHORITY_CHAIN_VIEW,
    NotionPageChainAdapter,
    build_notion_snapshot,
    compile_source_backed_view,
    validate_graph_ir,
)

EVIDENCE = Path(__file__).resolve().parents[1] / "fixtures" / "cartography" / "source-backed" / "notion-cartography-chain.2026-07-27.json"


class RecordingReadClient:
    def __init__(self, records):
        self.records = {record["id"]: deepcopy(record) for record in records}
        self.calls = []

    def fetch_page(self, page_id):
        self.calls.append(("fetch_page", page_id))
        return deepcopy(self.records[page_id])


def source_evidence():
    return json.loads(EVIDENCE.read_text(encoding="utf-8"))


def build_proof():
    evidence = source_evidence()
    client = RecordingReadClient(evidence["records"])
    result = NotionPageChainAdapter(client).read(evidence["root_page_id"], evidence["scope_key"])
    snapshot = build_notion_snapshot(
        result,
        scope_key=evidence["scope_key"],
        snapshot_id=evidence["evidence_id"],
        source_pointer=evidence["provenance"]["source_pointer"],
        source_modification_marker=evidence["observed_at"],
        created_at=evidence["observed_at"],
    )
    return evidence, client, result, snapshot


def test_real_source_chain_is_read_without_write_capabilities():
    evidence, client, result, _ = build_proof()
    assert len(result.records) == 4
    assert len(result.nodes) == 4
    assert len(result.edges) == 3
    assert not result.unresolved_references
    assert client.calls == [("fetch_page", record_id) for record_id in [
        evidence["root_page_id"],
        "3a943bd4-ae4a-81b0-ac3a-fa918812e811",
        "39e43bd4-ae4a-81c9-a650-f99e2bf6f09e",
        "39a43bd4-ae4a-8140-947f-d77dca982dda",
    ]]
    assert not hasattr(client, "update_page")
    assert not hasattr(client, "create_page")
    assert not hasattr(client, "delete_page")


def test_source_backed_snapshot_validates_and_is_deterministic():
    _, _, _, first = build_proof()
    _, _, _, second = build_proof()
    assert validate_graph_ir(first) == []
    assert first["snapshot_digest"] == second["snapshot_digest"]
    assert first["source_coverage"][0]["observed_objects"] == 4
    assert first["source_coverage"][0]["coverage_state"] == "COMPLETE"


def test_view_compiler_proof_retains_snapshot_provenance():
    _, _, _, snapshot = build_proof()
    compiled = compile_source_backed_view(snapshot, NOTION_AUTHORITY_CHAIN_VIEW)
    assert len(compiled["included_node_ids"]) == 4
    assert len(compiled["included_edge_ids"]) == 3
    assert compiled["source_snapshot_id"] == snapshot["snapshot_id"]
    assert compiled["source_snapshot_digest"] == snapshot["snapshot_digest"]
    assert compiled["source_coverage"] == snapshot["source_coverage"]
    assert "layout" not in compiled
    assert "coordinates" not in compiled


def test_adapter_fails_closed_on_source_cycle():
    evidence = source_evidence()
    records = deepcopy(evidence["records"])
    records[-1]["parent_id"] = evidence["root_page_id"]
    client = RecordingReadClient(records)
    with pytest.raises(ValueError, match="cycle"):
        NotionPageChainAdapter(client).read(evidence["root_page_id"], evidence["scope_key"])


def test_view_compiler_refuses_invalid_graph_ir():
    _, _, _, snapshot = build_proof()
    snapshot["nodes"][0]["attributes"]["position"] = {"x": 1, "y": 2}
    with pytest.raises(ValueError, match="invalid Graph IR"):
        compile_source_backed_view(snapshot, NOTION_AUTHORITY_CHAIN_VIEW)
