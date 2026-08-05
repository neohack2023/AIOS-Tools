from __future__ import annotations

import copy
import hashlib
import importlib.util
import json
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
MANIFEST_PATH = ROOT / "docs/evidence/AUDIO_STEM_SECTION_MODEL_LOCK_SLICE2A.json"
PROFILE_PATH = ROOT / "docs/evidence/AUDIO_STEM_SECTION_FROZEN_PROFILE_SLICE2A.json"
RESOURCE_PATH = ROOT / "docs/evidence/AUDIO_STEM_SECTION_RESOURCE_ENVELOPE_SLICE2A.json"
RUNTIME_PATH = ROOT / "docs/evidence/AUDIO_STEM_SECTION_RUNTIME_REVIEW_SLICE2A.json"
SCRIPT_PATH = ROOT / "scripts/verify_audio_model_lock.py"

spec = importlib.util.spec_from_file_location("verify_audio_model_lock", SCRIPT_PATH)
assert spec and spec.loader
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


def load(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def test_locked_manifest_and_cross_evidence_are_valid():
    manifest = load(MANIFEST_PATH)
    module.validate_manifest(manifest)
    module.validate_frozen_profile(manifest, load(PROFILE_PATH))
    module.validate_resource_receipt(manifest, load(RESOURCE_PATH))
    module.validate_runtime_review(manifest, load(RUNTIME_PATH))
    assert manifest["gates"]["runtime_admission"] is False
    assert manifest["gates"]["pilot_authorized"] is False


def test_wrong_notion_decision_link_is_rejected():
    data = load(MANIFEST_PATH)
    data["authority"]["notion_decision_candidate"] = data["authority"]["notion_parent_workflow"]
    with pytest.raises(module.VerificationError, match="Notion decision-candidate URL"):
        module.validate_manifest(data)


def test_missing_package_hash_is_rejected():
    data = load(MANIFEST_PATH)
    data["package_artifact"]["sha256"] = None
    with pytest.raises(module.VerificationError, match="package sha256"):
        module.validate_manifest(data)


def test_runtime_admission_claim_is_rejected():
    data = load(MANIFEST_PATH)
    data["gates"]["runtime_admission"] = True
    with pytest.raises(module.VerificationError, match="runtime_admission"):
        module.validate_manifest(data)


def test_weight_order_is_contractual():
    data = load(MANIFEST_PATH)
    data["weights"][0], data["weights"][1] = data["weights"][1], data["weights"][0]
    with pytest.raises(module.VerificationError, match="weight target order"):
        module.validate_manifest(data)


def test_frozen_profile_checksum_tamper_is_rejected():
    manifest = load(MANIFEST_PATH)
    profile = load(PROFILE_PATH)
    profile["inference"]["niter"] = 2
    with pytest.raises(module.VerificationError, match="checksum mismatch"):
        module.validate_frozen_profile(manifest, profile)


def test_resource_determinism_failure_is_rejected():
    manifest = load(MANIFEST_PATH)
    receipt = load(RESOURCE_PATH)
    receipt["inference"]["same_context_bit_identical"] = False
    with pytest.raises(module.VerificationError, match="deterministic rerun"):
        module.validate_resource_receipt(manifest, receipt)


def test_runtime_review_cannot_claim_implementation_present():
    manifest = load(MANIFEST_PATH)
    review = load(RUNTIME_PATH)
    review["implementation_present"] = True
    with pytest.raises(module.VerificationError, match="implementation absent"):
        module.validate_runtime_review(manifest, review)


def test_quarantine_weight_verification_success(tmp_path: Path):
    data = load(MANIFEST_PATH)
    fixture = copy.deepcopy(data)
    for item in fixture["weights"]:
        blob = f"{item['target']} fixture".encode()
        (tmp_path / item["filename"]).write_bytes(blob)
        item["provider_md5"] = hashlib.md5(blob, usedforsecurity=False).hexdigest()
        item["sha256"] = hashlib.sha256(blob).hexdigest()
        item["byte_size"] = len(blob)
    result = module.verify_weights(fixture, tmp_path)
    assert result["status"] == "QUARANTINE_WEIGHTS_VERIFIED"
    assert result["authority_transfer"] is False
    assert len(result["weights"]) == 4


def test_provider_md5_mismatch_fails(tmp_path: Path):
    data = load(MANIFEST_PATH)
    for item in data["weights"]:
        (tmp_path / item["filename"]).write_bytes(item["target"].encode())
    with pytest.raises(module.VerificationError, match="provider MD5 mismatch"):
        module.verify_weights(data, tmp_path)
