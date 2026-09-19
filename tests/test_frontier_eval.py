from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest

from aios_tools.benchmarks.frontier_eval import (
    EXPECTED_LANES,
    FrontierEvalError,
    execution_admission,
    fit_time_horizons,
    load_frontier_eval_contract,
    validate_result_pair,
)


ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "benchmarks" / "frontier_eval_01" / "manifest.v0.1.json"
SCHEMA = ROOT / "contracts" / "frontier-eval-manifest.v0.1.schema.json"
DIGEST = "a" * 64


def _load():
    return load_frontier_eval_contract(MANIFEST, SCHEMA)


def test_contract_freezes_exactly_four_paired_lanes() -> None:
    contract = _load()
    assert tuple(lane["id"] for lane in contract.manifest["lanes"]) == EXPECTED_LANES
    assert contract.manifest["pair_contract"]["treatments"] == ["DIRECT", "AIOS"]
    assert contract.manifest["pair_contract"]["allowed_difference"] == "scaffold_profile_only"
    assert contract.manifest["state"] == "NOT_EXECUTED"
    assert contract.manifest["score_status"] == "NO_SCORES"
    assert contract.manifest["official_claim_allowed"] is False


def test_lane_specific_freeze_requirements_are_present() -> None:
    contract = _load()
    capability = contract.lane("DEEPMIND_CAPABILITY_PORTFOLIO")
    assert len(capability["domains"]) == 10
    assert capability["human_baseline"]["population"] == "SKILLED_ADULTS"

    arc = contract.lane("ARC_AGI_3")
    assert arc["phase_order"][0] == "PUBLIC_ENVIRONMENTS"
    assert "raw_action_trace" in arc["required_artifacts"]
    assert "action_efficiency_score" in arc["required_artifacts"]

    metr = contract.lane("METR_STYLE_AUTONOMY")
    assert 24 <= metr["task_target"] <= 40
    assert sum(item["task_count"] for item in metr["duration_bands_minutes"]) == 32
    assert metr["runs_per_subject_per_task"] == 6
    assert metr["forced_restart"]["enabled"] is True
    assert metr["horizon_fit"]["probabilities"] == [0.5, 0.8]

    control = contract.lane("CONTROL_ARENA")
    assert len(control["attack_families"]) == 8
    assert control["sandbox_only"] is True
    assert control["monitor"]["calibration_false_positive_rate"] == 0.05


def test_profile_hash_tamper_fails_closed(tmp_path: Path) -> None:
    manifest = json.loads(MANIFEST.read_text())
    temp_root = tmp_path
    temp_manifest = temp_root / "benchmarks" / "frontier_eval_01" / "manifest.v0.1.json"
    temp_schema = temp_root / "contracts" / SCHEMA.name
    temp_manifest.parent.mkdir(parents=True)
    temp_schema.parent.mkdir(parents=True)
    (temp_manifest.parent / "profiles").mkdir()
    temp_manifest.write_text(json.dumps(manifest))
    temp_schema.write_text(SCHEMA.read_text())
    (temp_manifest.parent / "profiles" / "direct.v0.1.txt").write_text("tampered")
    (temp_manifest.parent / "profiles" / "aios-generic.v0.1.txt").write_text("tampered")
    with pytest.raises(FrontierEvalError, match="profile digest mismatch"):
        load_frontier_eval_contract(temp_manifest, temp_schema)


def test_admission_blocks_unresolved_model_bundles_graders_and_baselines() -> None:
    report = execution_admission(
        _load(),
        environ={},
        resource_acknowledgement=None,
        task_bundle_digests={},
        grader_digests={},
        human_baseline_digests={},
        runtime_image_digest=None,
    )
    assert report["status"] == "BLOCKED"
    assert report["score_status"] == "NO_SCORES"
    assert report["official_claim_allowed"] is False
    assert "model_identity_unresolved" in report["blocking_reasons"]
    assert "resource_acknowledgement_missing" in report["blocking_reasons"]


def test_admission_is_ready_only_with_all_frozen_bindings() -> None:
    lane_digests = {lane: DIGEST for lane in EXPECTED_LANES}
    report = execution_admission(
        _load(),
        environ={
            "AIOS_FRONTIER_EVAL_MODEL": "provider/model@immutable-revision",
            "AIOS_FRONTIER_EVAL_PROVIDER": "provider",
        },
        resource_acknowledgement="AIOS_FRONTIER_EVAL_01",
        task_bundle_digests=lane_digests,
        grader_digests=lane_digests,
        human_baseline_digests=lane_digests,
        runtime_image_digest=DIGEST,
    )
    assert report["status"] == "READY_TO_EXECUTE"
    assert report["blocking_reasons"] == []
    assert report["score_status"] == "NO_SCORES"


def _result(treatment: str) -> dict[str, object]:
    return {
        "evaluation_id": "AIOS_FRONTIER_EVAL_01",
        "freeze_digest": DIGEST,
        "lane_id": "ARC_AGI_3",
        "task_id": "public-env-01",
        "run_index": 1,
        "treatment": treatment,
        "provider": "provider",
        "model_identity": "provider/model@immutable-revision",
        "runtime_digest": DIGEST,
        "grader_digest": DIGEST,
        "human_minutes": 30.0,
        "authority_transfer": False,
        "artifacts": {
            "action_trace_sha256": DIGEST,
            "raw_result_sha256": DIGEST,
            "receipt_sha256": DIGEST,
        },
    }


def test_result_pair_rejects_mismatched_model_or_freeze() -> None:
    direct = _result("DIRECT")
    aios = _result("AIOS")
    validate_result_pair(direct, aios)
    changed = copy.deepcopy(aios)
    changed["model_identity"] = "different/model"
    with pytest.raises(FrontierEvalError, match="model_identity"):
        validate_result_pair(direct, changed)


def test_horizon_fit_reports_50_and_80_percent_minutes() -> None:
    attempts = []
    for minutes, successes in ((15, 6), (30, 5), (60, 4), (120, 2), (240, 1), (480, 0)):
        attempts.extend((minutes, index < successes) for index in range(6))
    fit = fit_time_horizons(attempts)
    assert fit["slope"] < 0
    assert fit["time_horizon_50_minutes"] > fit["time_horizon_80_minutes"] > 0
    assert fit["confidence_intervals_status"] == "REQUIRES_HIERARCHICAL_BOOTSTRAP"
