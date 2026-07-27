import json
from copy import deepcopy
from pathlib import Path

import pytest

from aios_tools.cartography import (
    DriveAncestorChainAdapter,
    ExactIdentityBinding,
    NotionPageChainAdapter,
    build_drive_snapshot,
    build_notion_snapshot,
    compare_cross_source_drift,
    resolve_exact_identities,
    validate_graph_ir,
)

ROOT = Path(__file__).resolve().parents[1]
NOTION_EVIDENCE = ROOT / "fixtures" / "cartography" / "source-backed" / "notion-cartography-chain.2026-07-27.json"
DRIVE_EVIDENCE = ROOT / "fixtures" / "cartography" / "source-backed" / "drive-cartography-chain.2026-07-27.json"


class RecordingNotionClient:
    def __init__(self, records):
        self.records = {record["id"]: deepcopy(record) for record in records}
        self.calls = []

    def fetch_page(self, page_id):
        self.calls.append(("fetch_page", page_id))
        return deepcopy(self.records[page_id])


class RecordingDriveClient:
    def __init__(self, records):
        self.records = {record["id"]: deepcopy(record) for record in records}
        self.calls = []

    def get_metadata(self, file_id):
        self.calls.append(("get_metadata", file_id))
        return deepcopy(self.records[file_id])


def load(path):
    return json.loads(path.read_text(encoding="utf-8"))


def build_proof():
    notion_evidence = load(NOTION_EVIDENCE)
    drive_evidence = load(DRIVE_EVIDENCE)

    notion_result = NotionPageChainAdapter(
        RecordingNotionClient(notion_evidence["records"])
    ).read(notion_evidence["root_page_id"], notion_evidence["scope_key"])
    notion_snapshot = build_notion_snapshot(
        notion_result,
        scope_key=notion_evidence["scope_key"],
        snapshot_id=notion_evidence["evidence_id"],
        source_pointer=notion_evidence["provenance"]["source_pointer"],
        source_modification_marker=notion_evidence["observed_at"],
        created_at=notion_evidence["observed_at"],
    )

    drive_client = RecordingDriveClient(drive_evidence["records"])
    drive_result = DriveAncestorChainAdapter(drive_client).read(
        drive_evidence["root_file_id"], drive_evidence["scope_key"]
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
    resolution = resolve_exact_identities(notion_snapshot, drive_snapshot, bindings)
    drift = compare_cross_source_drift(notion_snapshot, drive_snapshot, resolution)
    return drive_evidence, drive_client, drive_result, drive_snapshot, resolution, drift


def test_real_drive_chain_is_read_without_write_capabilities():
    evidence, client, result, snapshot, _, _ = build_proof()
    assert len(result.records) == 5
    assert len(result.nodes) == 5
    assert len(result.edges) == 4
    assert not result.unresolved_references
    assert client.calls == [("get_metadata", record["id"]) for record in evidence["records"]]
    assert not hasattr(client, "update_file")
    assert not hasattr(client, "upload_file")
    assert not hasattr(client, "delete_file")
    assert validate_graph_ir(snapshot) == []
    assert snapshot["source_coverage"][0]["adapter_id"] == "drive.ancestor_chain.read_only"


def test_drive_snapshot_and_resolution_are_deterministic():
    *_, first_resolution, first_drift = build_proof()
    *_, second_resolution, second_drift = build_proof()
    assert first_resolution == second_resolution
    assert first_drift == second_drift
    assert len(first_resolution["resolved"]) == 1
    assert not first_resolution["unresolved"]
    assert first_resolution["resolved"][0]["resolution_method"] == "EXACT_REGISTERED_BINDING"
    assert first_resolution["resolved"][0]["confidence"] == 1.0


def test_drift_preserves_notion_authority_and_drive_shadow():
    *_, drift = build_proof()
    comparison = drift["comparisons"][0]
    assert comparison["authority"] == "NOTION"
    assert comparison["shadow"] == "GOOGLE_DRIVE"
    assert comparison["state"] == "DRIFT_DETECTED"
    assert comparison["differences"][0]["classification"] == "DISPLAY_DRIFT"
    assert drift["drift_count"] == 1


def test_identity_resolution_never_matches_labels_without_binding():
    evidence, _, _, drive_snapshot, _, _ = build_proof()
    notion_evidence = load(NOTION_EVIDENCE)
    notion_result = NotionPageChainAdapter(
        RecordingNotionClient(notion_evidence["records"])
    ).read(notion_evidence["root_page_id"], notion_evidence["scope_key"])
    notion_snapshot = build_notion_snapshot(
        notion_result,
        scope_key=notion_evidence["scope_key"],
        snapshot_id=notion_evidence["evidence_id"],
        source_pointer=notion_evidence["provenance"]["source_pointer"],
        source_modification_marker=notion_evidence["observed_at"],
        created_at=notion_evidence["observed_at"],
    )
    assert resolve_exact_identities(notion_snapshot, drive_snapshot, [])["resolved"] == []
    bad = ExactIdentityBinding(
        notion_source_object_id="missing-notion-id",
        drive_source_object_id=evidence["root_file_id"],
        evidence_pointer="negative fixture",
        binding_key="no-label-fallback",
    )
    result = resolve_exact_identities(notion_snapshot, drive_snapshot, [bad])
    assert not result["resolved"]
    assert result["unresolved"][0]["missing_sources"] == ["notion"]


def test_drive_adapter_fails_closed_on_multiple_parents_and_cycles():
    evidence = load(DRIVE_EVIDENCE)
    records = deepcopy(evidence["records"])
    records[0]["parent_ids"] = ["parent-a", "parent-b"]
    with pytest.raises(ValueError, match="multiple parents"):
        DriveAncestorChainAdapter(RecordingDriveClient(records)).read(
            evidence["root_file_id"], evidence["scope_key"]
        )

    records = deepcopy(evidence["records"])
    records[-1]["parent_ids"] = [evidence["root_file_id"]]
    with pytest.raises(ValueError, match="cycle"):
        DriveAncestorChainAdapter(RecordingDriveClient(records)).read(
            evidence["root_file_id"], evidence["scope_key"]
        )
