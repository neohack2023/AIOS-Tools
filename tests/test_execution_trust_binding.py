import copy
import json
from pathlib import Path

from jsonschema import Draft202012Validator

from aios_tools.experimental.execution_trust_binding import (
    admit_and_invoke_read_only,
    build_system_health_binding,
    evaluate_trust_binding,
    load_synthetic_matrix,
    run_synthetic_matrix,
)


EXPECTED_CASES = [f"ETB-{index:02d}" for index in range(1, 11)]


def _case(case_id: str) -> dict:
    return next(case for case in load_synthetic_matrix() if case["id"] == case_id)


def test_frozen_etb_01_through_etb_10_matrix_passes():
    result = run_synthetic_matrix()

    assert result["passed"] is True
    assert result["case_count"] == 10
    assert [case["id"] for case in result["cases"]] == EXPECTED_CASES
    assert all(case["passed"] for case in result["cases"])
    assert result["authority_transfer"] is False


def test_etb_05_preserves_remote_controller_local_worker_asymmetry():
    case = _case("ETB-05")
    receipt = evaluate_trust_binding(case["binding"])

    topology = receipt["observed_runtime_topology"]
    assert receipt["trust_decision"] == "ADMIT"
    assert topology["controller_location"] == "REMOTE_VENDOR_CONTROL_PLANE"
    assert topology["tool_execution_location"] == "LOCAL_CUSTOMER_WORKER"
    assert topology["credential_audience"] == "LOCAL_WORKER_ONLY"
    assert topology["data_egress_policy_id"] == "EGRESS-METADATA-ONLY-01"


def test_etb_07_revocation_authorizes_zero_authenticated_requests():
    receipt = evaluate_trust_binding(_case("ETB-07")["binding"])

    assert receipt["trust_decision"] == "BLOCK"
    assert receipt["executor_invocation_authorized"] is False
    assert receipt["authenticated_requests_authorized"] == 0


def test_etb_08_security_pass_does_not_promote_semantic_authority():
    receipt = evaluate_trust_binding(_case("ETB-08")["binding"])

    assert receipt["trust_decision"] == "ADMIT"
    assert receipt["security_trust"]["result"] == "PASS"
    assert receipt["semantic_authority"]["authority_class"] == "RESEARCH_ONLY"
    assert receipt["semantic_authority"]["canon_or_trusted_promotion_allowed"] is False
    assert receipt["security_trust_grants_semantic_authority"] is False


def test_malformed_binding_fails_closed_before_field_evaluation():
    receipt = evaluate_trust_binding({"schema": "wrong"})

    assert receipt["trust_decision"] == "UNKNOWN"
    assert receipt["admitted"] is False
    assert receipt["executor_invocation_authorized"] is False
    assert receipt["reason_codes"] == ["BINDING_SCHEMA_INVALID"]
    assert receipt["validation_errors"]


def test_trust_receipt_is_deterministic_for_same_binding():
    binding = _case("ETB-10")["binding"]

    first = evaluate_trust_binding(binding)
    second = evaluate_trust_binding(copy.deepcopy(binding))

    assert first == second


def test_non_admitted_binding_never_invokes_executor():
    called = False

    def should_not_run(*_args, **_kwargs):
        nonlocal called
        called = True
        raise AssertionError("blocked executor was invoked")

    path = admit_and_invoke_read_only(
        _case("ETB-04")["binding"],
        "system.health",
        {},
        executor=should_not_run,
    )

    assert path["path_status"] == "BLOCKED"
    assert path["executor_invoked"] is False
    assert called is False


def test_real_system_health_binding_validates_and_executes_shared_core():
    binding = build_system_health_binding()
    binding_schema = json.loads(
        Path("contracts/execution-trust-binding.v0.1.schema.json").read_text(
            encoding="utf-8"
        )
    )
    assert list(Draft202012Validator(binding_schema).iter_errors(binding)) == []

    path = admit_and_invoke_read_only(binding, "system.health", {})

    assert path["path_status"] == "COMPLETED"
    assert path["executor_invoked"] is True
    assert path["gate_errors"] == []
    assert path["trust_receipt"]["trust_decision"] == "ADMIT"
    assert path["trust_receipt"]["authority_transfer"] is False
    assert path["tool_receipt"]["status"] == "COMPLETED"
    assert path["tool_receipt"]["tool"] == "system.health"
    assert path["tool_receipt"]["mode"] == "READ_ONLY"
    assert path["tool_receipt"]["effect_class"] == "NO_EXTERNAL_EFFECT"
    assert path["tool_receipt"]["external_effects"] == []
    assert path["tool_receipt"]["authority_transfer"] is False
    assert (
        path["tool_receipt"]["authority_context"]["trust_binding_receipt_id"]
        == path["trust_receipt"]["trust_receipt_id"]
    )


def test_real_path_detects_runtime_version_rebinding_before_executor():
    binding = build_system_health_binding()
    binding["asset_or_tool_identity"]["version_label"] = "stale-version"
    called = False

    def should_not_run(*_args, **_kwargs):
        nonlocal called
        called = True
        raise AssertionError("stale executor was invoked")

    path = admit_and_invoke_read_only(
        binding, "system.health", {}, executor=should_not_run
    )

    assert path["path_status"] == "BLOCKED"
    assert path["executor_invoked"] is False
    assert "BOUND_TOOL_VERSION_STALE" in path["gate_errors"]
    assert called is False


def test_stronger_effect_requires_positive_security_evidence():
    binding = _case("ETB-10")["binding"]
    binding["requested_operation"].update(
        {
            "action": "EXECUTE_WRITE",
            "mode": "WRITE",
            "effect_class": "LOCAL_DURABLE_WRITE",
        }
    )
    binding["security_trust"]["result"] = "NOT_APPLICABLE"

    receipt = evaluate_trust_binding(binding)

    assert receipt["trust_decision"] == "BLOCK"
    assert "SECURITY_EVIDENCE_REQUIRED_FOR_STRONGER_EFFECT" in receipt["reason_codes"]
