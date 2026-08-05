from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from aios_tools.audio_runtime import (
    AudioRuntimeError,
    PROFILE_CHECKSUM,
    PROFILE_ID,
    TOOL_IDENTITY,
    parse_slice1_receipt,
    preflight_audio_runtime,
    reject_prompt_leak,
    validate_request_contract,
    verify_frozen_profile,
    verify_model_cache,
    verify_output_boundary,
)
from aios_tools.canonical import canonical_sha256

ROOT = Path(__file__).resolve().parents[1]
FROZEN_PROFILE_PATH = ROOT / "docs/evidence/AUDIO_STEM_SECTION_FROZEN_PROFILE_SLICE2A.json"


def _sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _receipt(run_id: str, source_sha256: str) -> str:
    return f"""# Slice 1 Run Receipt: {run_id}

- **Status:** `COMPLETE`
- **Human review:** `PENDING`
- **Scope:** `udio-algorithms`
- **Track:** `TEST_TRACK`
- **Profile:** `slice1-baseline-v0.1`
- **Created UTC:** `2026-08-05T01:52:40Z`
- **Source SHA-256:** `{source_sha256}`

## Governance

- Evidence class remains `STONE_CANDIDATE`.
- Canon promotion remains disabled.
- Human review is required before acceptance.
"""


def _payload(tmp_path: Path, source: Path, receipt: Path, cache: Path) -> dict:
    source_sha = _sha(source.read_bytes())
    return {
        "source_audio_path": str(source.resolve()),
        "source_sha256": source_sha,
        "slice1_run_id": "S1-TEST-001",
        "slice1_receipt_path": str(receipt.resolve()),
        "slice1_source_sha256": source_sha,
        "profile_id": PROFILE_ID,
        "profile_path": str(FROZEN_PROFILE_PATH.resolve()),
        "profile_checksum": PROFILE_CHECKSUM,
        "model_cache_directory": str(cache.resolve()),
        "output_directory": str((tmp_path / "result").resolve()),
        "scope_key": "udio-algorithms",
        "requested_by": {"type": "HUMAN", "id": "pytest"},
        "authority_transfer": False,
    }


def test_committed_frozen_profile_checksum_is_valid():
    payload = {"profile_id": PROFILE_ID, "profile_checksum": PROFILE_CHECKSUM}
    profile = verify_frozen_profile(payload, FROZEN_PROFILE_PATH)
    assert profile["tool_identity"] == TOOL_IDENTITY
    assert profile["inference"]["network_during_analysis"] is False
    assert profile["inference"]["authority_transfer"] is False


def test_slice1_markdown_receipt_parses_exact_dependency_fields(tmp_path: Path):
    source_sha = "a" * 64
    path = tmp_path / "run_receipt.md"
    path.write_text(_receipt("S1-TEST-001", source_sha), encoding="utf-8")
    parsed = parse_slice1_receipt(path)
    assert parsed["run_id"] == "S1-TEST-001"
    assert parsed["status"] == "COMPLETE"
    assert parsed["profile_id"] == "slice1-baseline-v0.1"
    assert parsed["source_sha256"] == source_sha


def test_prompt_metadata_is_rejected_before_blind_processing():
    with pytest.raises(AudioRuntimeError) as exc:
        reject_prompt_leak({"nested": {"lyrics": "not allowed"}})
    assert exc.value.code == "PROMPT_LEAK_INTO_BLIND_PASS"


def test_request_contract_rejects_undocumented_override(tmp_path: Path):
    source = tmp_path / "source.wav"
    source.write_bytes(b"audio")
    receipt = tmp_path / "receipt.md"
    receipt.write_text(_receipt("S1-TEST-001", _sha(b"audio")), encoding="utf-8")
    cache = tmp_path / "cache"
    cache.mkdir()
    payload = _payload(tmp_path, source, receipt, cache)
    payload["model_override"] = "other-model"
    with pytest.raises(AudioRuntimeError) as exc:
        validate_request_contract(payload)
    assert exc.value.code == "REQUEST_CONTRACT_INVALID"


def test_output_overwrite_is_rejected(tmp_path: Path):
    output = tmp_path / "existing"
    output.mkdir()
    with pytest.raises(AudioRuntimeError) as exc:
        verify_output_boundary(str(output.resolve()))
    assert exc.value.code == "OUTPUT_OVERWRITE_BLOCKED"


def test_output_symlink_boundary_is_rejected(tmp_path: Path):
    real_parent = tmp_path / "real"
    real_parent.mkdir()
    linked_parent = tmp_path / "linked"
    try:
        linked_parent.symlink_to(real_parent, target_is_directory=True)
    except (OSError, NotImplementedError):
        pytest.skip("symlinks are unavailable in this execution context")
    with pytest.raises(AudioRuntimeError) as exc:
        verify_output_boundary(str((linked_parent / "result").absolute()))
    assert exc.value.code == "SYMLINK_BOUNDARY_REJECTED"


def test_model_cache_hashes_all_locked_artifacts(tmp_path: Path):
    cache = tmp_path / "cache"
    package_dir = cache / "package"
    weights_dir = cache / "weights"
    package_dir.mkdir(parents=True)
    weights_dir.mkdir()

    package_blob = b"wheel fixture"
    package_path = package_dir / "openunmix-fixture.whl"
    package_path.write_bytes(package_blob)
    weights = []
    for target in ["vocals", "drums", "bass", "other"]:
        blob = f"{target} fixture".encode()
        filename = f"{target}.pth"
        (weights_dir / filename).write_bytes(blob)
        weights.append({"target": target, "filename": filename, "sha256": _sha(blob), "byte_size": len(blob)})

    profile = {
        "package": {
            "filename": package_path.name,
            "sha256": _sha(package_blob),
            "byte_size": len(package_blob),
        },
        "weights": weights,
    }
    result = verify_model_cache(profile, cache.resolve())
    assert result["network_during_analysis"] is False
    assert [item["target"] for item in result["weights"]] == ["vocals", "drums", "bass", "other"]


def test_model_cache_checksum_mismatch_fails_closed(tmp_path: Path):
    cache = tmp_path / "cache"
    (cache / "package").mkdir(parents=True)
    (cache / "weights").mkdir()
    package = cache / "package" / "fixture.whl"
    package.write_bytes(b"actual")
    profile = {
        "package": {"filename": "fixture.whl", "sha256": _sha(b"different"), "byte_size": 6},
        "weights": [
            {"target": target, "filename": f"{target}.pth", "sha256": "0" * 64, "byte_size": 1}
            for target in ["vocals", "drums", "bass", "other"]
        ],
    }
    with pytest.raises(AudioRuntimeError) as exc:
        verify_model_cache(profile, cache.resolve())
    assert exc.value.code == "ARTIFACT_CHECKSUM_MISMATCH"


def test_profile_tamper_is_rejected(tmp_path: Path):
    profile = json.loads(FROZEN_PROFILE_PATH.read_text(encoding="utf-8"))
    profile["inference"]["niter"] = 2
    path = tmp_path / "profile.json"
    path.write_text(json.dumps(profile), encoding="utf-8")
    with pytest.raises(AudioRuntimeError) as exc:
        verify_frozen_profile({"profile_id": PROFILE_ID, "profile_checksum": PROFILE_CHECKSUM}, path)
    assert exc.value.code == "PROFILE_CHECKSUM_MISMATCH"


def test_preflight_orchestrates_without_writing_or_loading_model(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    source = tmp_path / "source.mp3"
    source.write_bytes(b"bounded source fixture")
    source_sha = _sha(source.read_bytes())
    receipt = tmp_path / "run_receipt.md"
    receipt.write_text(_receipt("S1-TEST-001", source_sha), encoding="utf-8")
    cache = tmp_path / "cache"
    cache.mkdir()
    payload = _payload(tmp_path, source, receipt, cache)

    fake_package = {"filename": "openunmix.whl", "sha256": "1" * 64, "byte_size": 1}
    fake_weights = [
        {"target": target, "filename": f"{target}.pth", "sha256": str(index + 2) * 64, "byte_size": 1}
        for index, target in enumerate(["vocals", "drums", "bass", "other"])
    ]

    def fake_verify_model_cache(profile: dict, cache_directory: Path) -> dict:
        assert profile["profile_checksum"] == PROFILE_CHECKSUM
        return {
            "directory": str(cache_directory),
            "package": fake_package,
            "weights": fake_weights,
            "network_during_analysis": False,
            "evidence_class": "ENVIRONMENT_RECEIPT",
        }

    monkeypatch.setattr("aios_tools.audio_runtime.verify_model_cache", fake_verify_model_cache)
    result = preflight_audio_runtime(payload)
    assert result["status"] == "PRECHECK_COMPLETE"
    assert result["runtime_admission"] is False
    assert result["pilot_authorized"] is False
    assert result["authority_transfer"] is False
    assert not Path(result["output_transaction"]["output_directory"]).exists()


def test_fake_profile_checksum_helper_matches_runtime_algorithm():
    unsigned = {
        "profile_id": PROFILE_ID,
        "tool_identity": TOOL_IDENTITY,
        "profile_state": "FROZEN_NOT_RUNTIME_ADMITTED",
        "inference": {"targets": ["vocals", "drums", "bass", "other"]},
    }
    assert canonical_sha256(unsigned) == hashlib.sha256(
        json.dumps(unsigned, ensure_ascii=False, allow_nan=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()
