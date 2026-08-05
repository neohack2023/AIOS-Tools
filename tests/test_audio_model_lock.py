from __future__ import annotations

import hashlib
import importlib.util
import json
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
MANIFEST_PATH = ROOT / "docs/evidence/AUDIO_STEM_SECTION_MODEL_LOCK_SLICE2A.json"
SCRIPT_PATH = ROOT / "scripts/verify_audio_model_lock.py"

spec = importlib.util.spec_from_file_location("verify_audio_model_lock", SCRIPT_PATH)
assert spec and spec.loader
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


def load_manifest():
    return json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))


def test_candidate_manifest_is_fail_closed_and_valid():
    data = load_manifest()
    module.validate_manifest(data)
    assert data["authority"]["authority_transfer"] is False
    assert data["runtime_reference"]["network_during_analysis"] is False
    assert data["gates"]["runtime_admission"] is False
    assert data["gates"]["pilot_authorized"] is False


def test_wrong_notion_decision_link_is_rejected():
    data = load_manifest()
    data["authority"]["notion_decision_candidate"] = data["authority"]["notion_parent_workflow"]
    with pytest.raises(module.VerificationError, match="Notion decision-candidate URL"):
        module.validate_manifest(data)


def test_runtime_admission_without_weight_hashes_is_rejected():
    data = load_manifest()
    data["gates"]["runtime_admission"] = True
    with pytest.raises(module.VerificationError, match="runtime admission"):
        module.validate_manifest(data)


def test_weight_order_is_contractual():
    data = load_manifest()
    data["weights"][0], data["weights"][1] = data["weights"][1], data["weights"][0]
    with pytest.raises(module.VerificationError, match="weight target order"):
        module.validate_manifest(data)


def test_quarantine_weight_verification_success(tmp_path: Path):
    data = load_manifest()
    contents = {
        "vocals": b"vocals fixture",
        "drums": b"drums fixture",
        "bass": b"bass fixture",
        "other": b"other fixture",
    }
    for item in data["weights"]:
        blob = contents[item["target"]]
        (tmp_path / item["filename"]).write_bytes(blob)
        item["provider_md5"] = hashlib.md5(blob, usedforsecurity=False).hexdigest()
        item["sha256"] = hashlib.sha256(blob).hexdigest()
        item["byte_size"] = len(blob)
        item["admitted"] = True
    data["gates"]["all_weight_sha256_present"] = True
    module.validate_manifest(data)
    result = module.verify_weights(data, tmp_path)
    assert result["status"] == "QUARANTINE_WEIGHTS_VERIFIED"
    assert result["authority_transfer"] is False
    assert len(result["weights"]) == 4


def test_provider_md5_mismatch_fails(tmp_path: Path):
    data = load_manifest()
    for item in data["weights"]:
        (tmp_path / item["filename"]).write_bytes(item["target"].encode())
    with pytest.raises(module.VerificationError, match="provider MD5 mismatch"):
        module.verify_weights(data, tmp_path)
