from __future__ import annotations

import copy
import hashlib
import inspect
import json
from pathlib import Path
from typing import Any, Callable

from jsonschema import Draft202012Validator

from .canonical import canonical_sha256
from .config import load_policy, load_registry
from .tools import HANDLERS


CONTRACT_ID = "AIOS_EXECUTION_TRUST_BINDING_01"
SCHEMA_ID = "aios.execution-trust-binding.v0.1"
EVALUATOR_VERSION = "execution-trust-binding/1.0.0"
ROOT = Path(__file__).resolve().parents[2]
SCHEMA_PATH = ROOT / "contracts" / "execution-trust-binding.v0.1.schema.json"
MATRIX_PATH = ROOT / "fixtures" / "execution-trust-binding" / "etb-matrix.v0.1.json"

_DECISION_PRIORITY = {
    "ADMIT": 0,
    "UNKNOWN": 1,
    "PENDING_POLICY": 2,
    "STALE": 3,
    "BLOCK": 4,
}


def _schema() -> dict[str, Any]:
    return json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))


def _validation_errors(binding: dict[str, Any]) -> list[dict[str, Any]]:
    errors = sorted(
        Draft202012Validator(_schema()).iter_errors(binding),
        key=lambda error: (list(error.absolute_path), error.message),
    )
    return [
        {
            "path": list(error.absolute_path),
            "validator": error.validator,
            "message": error.message,
        }
        for error in errors
    ]


def _stronger(current: str, candidate: str) -> str:
    if _DECISION_PRIORITY[candidate] > _DECISION_PRIORITY[current]:
        return candidate
    return current


def _add_reason(reasons: list[str], code: str) -> None:
    if code not in reasons:
        reasons.append(code)


def evaluate_trust_binding(binding: dict[str, Any]) -> dict[str, Any]:
    """Evaluate one trust binding without invoking any executor.

    The evaluator remains independent from execution. It composes existing
    evidence into an admission decision but grants no policy, capability,
    consent, credential, or semantic authority.
    """

    binding_digest = canonical_sha256(binding)
    validation_errors = _validation_errors(binding)
    if validation_errors:
        decision = "UNKNOWN"
        reasons = ["BINDING_SCHEMA_INVALID"]
        receipt_seed = {
            "evaluator_version": EVALUATOR_VERSION,
            "binding_digest": binding_digest,
            "trust_decision": decision,
            "reason_codes": reasons,
        }
        return {
            "schema": "aios.execution-trust-receipt.v0.1",
            "trust_receipt_id": f"etb-receipt-{canonical_sha256(receipt_seed)}",
            "contract_id": CONTRACT_ID,
            "evaluator_version": EVALUATOR_VERSION,
            "execution_id": binding.get("execution_id", "UNKNOWN"),
            "binding_digest": binding_digest,
            "trust_decision": decision,
            "admitted": False,
            "executor_invocation_authorized": False,
            "reason_codes": reasons,
            "validation_errors": validation_errors,
            "authority_transfer": False,
        }

    decision = "ADMIT"
    reasons: list[str] = []
    identity = binding["asset_or_tool_identity"]
    catalog = binding["catalog_state"]
    policy = binding["policy_state"]
    security = binding["security_trust"]
    requested = binding["requested_operation"]
    extension = binding["extension_binding"]
    producer = binding["producer_lineage"]
    semantic = binding["semantic_authority"]
    skill = binding["skill_compounding"]
    observation = binding["runtime_observation"]

    discovered = catalog["discovered_state"]
    if discovered == "NEW_PENDING_POLICY":
        decision = _stronger(decision, "PENDING_POLICY")
        _add_reason(reasons, "NEW_TOOL_PENDING_POLICY")
    elif discovered == "REMOVED":
        decision = _stronger(decision, "BLOCK")
        _add_reason(reasons, "REMOVED_TOOL_BLOCKED")
    elif discovered == "UNKNOWN":
        decision = _stronger(decision, "UNKNOWN")
        _add_reason(reasons, "CATALOG_STATE_UNKNOWN")

    if catalog["freshness"] == "STALE":
        decision = _stronger(decision, "STALE")
        _add_reason(reasons, "CATALOG_STALE")
    elif catalog["freshness"] == "UNKNOWN":
        decision = _stronger(decision, "UNKNOWN")
        _add_reason(reasons, "CATALOG_FRESHNESS_UNKNOWN")

    if identity["content_digest"] != identity["expected_content_digest"]:
        decision = _stronger(decision, "STALE")
        _add_reason(reasons, "SAME_VERSION_DIGEST_DRIFT")
    if identity["dependency_manifest_digest"] != identity["expected_dependency_manifest_digest"]:
        decision = _stronger(decision, "STALE")
        _add_reason(reasons, "DEPENDENCY_MANIFEST_DRIFT")

    schema_drift = catalog["schema_digest"] != catalog["expected_schema_digest"]
    description_drift = catalog["description_digest"] != catalog["expected_description_digest"]
    if schema_drift or description_drift:
        decision = _stronger(decision, "STALE")
        _add_reason(reasons, "MATERIAL_TOOL_IDENTITY_DRIFT")
        if requested["mode"] == "WRITE":
            _add_reason(reasons, "READ_TO_WRITE_SCHEMA_DRIFT_CONSENT_INVALIDATED")

    if policy["decision"] == "DENY":
        decision = _stronger(decision, "BLOCK")
        _add_reason(reasons, "POLICY_DENIED")
    elif policy["decision"] == "UNKNOWN":
        decision = _stronger(decision, "PENDING_POLICY")
        _add_reason(reasons, "POLICY_UNRESOLVED")

    consent = policy["consent"]
    if consent in {"REQUIRED_PENDING", "UNKNOWN"}:
        decision = _stronger(decision, "PENDING_POLICY")
        _add_reason(reasons, "CONSENT_UNRESOLVED")
    elif consent == "DENIED":
        decision = _stronger(decision, "BLOCK")
        _add_reason(reasons, "CONSENT_DENIED")

    if security["result"] == "BLOCK":
        decision = _stronger(decision, "BLOCK")
        _add_reason(reasons, "SECURITY_VALIDATION_BLOCK")
    elif security["result"] == "UNKNOWN":
        decision = _stronger(decision, "UNKNOWN")
        _add_reason(reasons, "SECURITY_TRUST_UNKNOWN")

    stronger_effect = (
        requested["mode"] == "WRITE"
        or requested["artifact_upload"]
        or requested["semantic_promotion"]
        or requested["skill_installation"]
        or requested["authenticated_requests"] > 0
    )
    if stronger_effect and security["result"] != "PASS":
        decision = _stronger(decision, "BLOCK")
        _add_reason(reasons, "SECURITY_EVIDENCE_REQUIRED_FOR_STRONGER_EFFECT")

    if requested["mode"] == "READ_ONLY" and requested["effect_class"] in {
        "LOCAL_DURABLE_WRITE",
        "REMOTE_MUTATION_REVERSIBLE",
        "REMOTE_MUTATION_HIGH_IMPACT",
    }:
        decision = _stronger(decision, "BLOCK")
        _add_reason(reasons, "MODE_EFFECT_CLASS_CONFLICT")
    if requested["mode"] == "WRITE" and requested["effect_class"] in {
        "NO_EXTERNAL_EFFECT",
        "READ_NETWORK",
    }:
        decision = _stronger(decision, "BLOCK")
        _add_reason(reasons, "MODE_EFFECT_CLASS_CONFLICT")

    for dependency in binding["artifact_dependencies"]:
        if dependency["digest"] != dependency["approved_digest"]:
            decision = _stronger(decision, "BLOCK")
            _add_reason(reasons, "TRANSITIVE_DEPENDENCY_DIGEST_UNAPPROVED")
        if dependency["security_result"] != "PASS":
            decision = _stronger(decision, "BLOCK")
            _add_reason(reasons, "TRANSITIVE_DEPENDENCY_BLOCKED")

    if binding["runtime_topology"] != observation["topology"]:
        decision = _stronger(decision, "BLOCK")
        _add_reason(reasons, "RUNTIME_TOPOLOGY_DRIFT")

    if requested["artifact_upload"] and not observation["egress_enabled"]:
        decision = _stronger(decision, "BLOCK")
        _add_reason(reasons, "EGRESS_DISABLED_ARTIFACT_UPLOAD_BLOCKED")

    if extension["enablement_state"] == "REVOKED":
        decision = _stronger(decision, "BLOCK")
        _add_reason(reasons, "EXTENSION_REVOKED")
    elif identity["kind"] == "BROWSER_EXTENSION" and extension["enablement_state"] == "UNKNOWN":
        decision = _stronger(decision, "UNKNOWN")
        _add_reason(reasons, "EXTENSION_ENABLEMENT_UNKNOWN")
    elif identity["kind"] == "BROWSER_EXTENSION" and extension["enablement_state"] == "ENABLED":
        required_extension_fields = (
            extension["extension_id"],
            extension["resolved_revision"],
            extension["manifest_digest"],
            extension["backend_scope"],
        )
        if any(value is None for value in required_extension_fields):
            decision = _stronger(decision, "BLOCK")
            _add_reason(reasons, "EXTENSION_BINDING_INCOMPLETE")

    if identity["kind"] == "GENERATED_ARTIFACT":
        if producer["producer_execution_id"] is None or not producer["source_receipt_ids"]:
            decision = _stronger(decision, "BLOCK")
            _add_reason(reasons, "PRODUCER_LINEAGE_INCOMPLETE")

    if requested["semantic_promotion"] and not semantic["canon_or_trusted_promotion_allowed"]:
        decision = _stronger(decision, "BLOCK")
        _add_reason(reasons, "SEMANTIC_PROMOTION_NOT_AUTHORIZED")

    if requested["skill_installation"]:
        if skill["held_out_validation"] != "PASS":
            decision = _stronger(decision, "BLOCK")
            _add_reason(reasons, "HELD_OUT_VALIDATION_FAILED")
        if not skill["install_authorized"]:
            decision = _stronger(decision, "BLOCK")
            _add_reason(reasons, "SKILL_INSTALLATION_NOT_AUTHORIZED")

    for event in binding["invalidation_events"]:
        if event in {"tool.catalog.changed", "artifact.digest.changed", "artifact.dependency.changed", "runtime.topology.changed", "runtime.egress_policy.changed", "browser.extension.changed", "skill.validation_dependency.changed", "authority.scope.changed"}:
            decision = _stronger(decision, "STALE")
            _add_reason(reasons, "MATERIAL_INVALIDATION_REQUIRES_REEVALUATION")
        elif event in {"tool.policy.changed", "tool.consent.changed"}:
            decision = _stronger(decision, "PENDING_POLICY")
            _add_reason(reasons, "POLICY_INVALIDATION_REQUIRES_REBINDING")
        elif event == "browser.extension.revoked":
            decision = _stronger(decision, "BLOCK")
            _add_reason(reasons, "EXTENSION_REVOKED")

    admitted = decision == "ADMIT"
    if admitted:
        _add_reason(reasons, "ALL_MATERIAL_BINDINGS_RESOLVED")

    authenticated_authorized = requested["authenticated_requests"] if admitted else 0
    if extension["enablement_state"] == "REVOKED":
        authenticated_authorized = 0

    receipt_seed = {
        "evaluator_version": EVALUATOR_VERSION,
        "binding_digest": binding_digest,
        "trust_decision": decision,
        "reason_codes": reasons,
    }
    return {
        "schema": "aios.execution-trust-receipt.v0.1",
        "trust_receipt_id": f"etb-receipt-{canonical_sha256(receipt_seed)}",
        "contract_id": CONTRACT_ID,
        "evaluator_version": EVALUATOR_VERSION,
        "execution_id": binding["execution_id"],
        "scope_key": binding["scope_key"],
        "capability_id": binding["capability_id"],
        "principal_id": binding["principal_id"],
        "asset_or_tool_identity": copy.deepcopy(identity),
        "catalog_revision": catalog["catalog_revision"],
        "policy_id": policy["policy_id"],
        "policy_version": policy["policy_version"],
        "binding_digest": binding_digest,
        "trust_decision": decision,
        "admitted": admitted,
        "executor_invocation_authorized": admitted,
        "reason_codes": reasons,
        "validation_errors": [],
        "observed_runtime_topology": copy.deepcopy(observation["topology"]),
        "semantic_authority": copy.deepcopy(semantic),
        "security_trust": copy.deepcopy(security),
        "artifact_upload_authorized": bool(admitted and requested["artifact_upload"] and observation["egress_enabled"]),
        "authenticated_requests_authorized": authenticated_authorized,
        "skill_installation_authorized": bool(admitted and requested["skill_installation"] and skill["held_out_validation"] == "PASS" and skill["install_authorized"]),
        "security_trust_grants_semantic_authority": False,
        "authority_transfer": False,
    }


def _deep_merge(base: dict[str, Any], overlay: dict[str, Any]) -> dict[str, Any]:
    merged = copy.deepcopy(base)
    for key, value in overlay.items():
        if isinstance(value, dict) and isinstance(merged.get(key), dict):
            merged[key] = _deep_merge(merged[key], value)
        else:
            merged[key] = copy.deepcopy(value)
    return merged


def load_synthetic_matrix(path: Path = MATRIX_PATH) -> list[dict[str, Any]]:
    document = json.loads(path.read_text(encoding="utf-8"))
    if document.get("schema") != "aios.execution-trust-binding-matrix.v0.1":
        raise ValueError("unexpected ETB matrix schema")
    base = document.get("base_binding")
    cases = document.get("cases")
    if not isinstance(base, dict) or not isinstance(cases, list):
        raise ValueError("ETB matrix requires base_binding and cases")
    materialized = []
    for case in cases:
        if not isinstance(case, dict) or not isinstance(case.get("overlay"), dict):
            raise ValueError("ETB matrix case is malformed")
        materialized.append(
            {
                "id": case["id"],
                "label": case["label"],
                "binding": _deep_merge(base, case["overlay"]),
                "expected": copy.deepcopy(case["expected"]),
            }
        )
    return materialized


def run_synthetic_matrix(path: Path = MATRIX_PATH) -> dict[str, Any]:
    cases = []
    for case in load_synthetic_matrix(path):
        receipt = evaluate_trust_binding(case["binding"])
        expected = case["expected"]
        checks = {
            "decision": receipt["trust_decision"] == expected["trust_decision"],
            "admitted": receipt["admitted"] is expected["admitted"],
            "required_reasons": set(expected.get("reason_codes", [])).issubset(receipt["reason_codes"]),
        }
        cases.append(
            {
                "id": case["id"],
                "label": case["label"],
                "passed": all(checks.values()),
                "checks": checks,
                "receipt": receipt,
            }
        )
    return {
        "schema": "aios.execution-trust-binding-matrix-result.v0.1",
        "contract_id": CONTRACT_ID,
        "evaluator_version": EVALUATOR_VERSION,
        "matrix_digest": canonical_sha256(json.loads(path.read_text(encoding="utf-8"))),
        "passed": all(case["passed"] for case in cases),
        "case_count": len(cases),
        "cases": cases,
        "authority_transfer": False,
    }


def _file_sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _tool_content_digest(metadata: dict[str, Any], handler: Callable[..., Any]) -> str:
    return canonical_sha256(
        {
            "metadata": metadata,
            "handler_source": inspect.getsource(handler),
        }
    )


def build_system_health_binding() -> dict[str, Any]:
    registry, registry_version = load_registry(HANDLERS)
    policy = load_policy()
    metadata = registry["system.health"]
    tool_digest = _tool_content_digest(metadata, HANDLERS["system.health"])
    dependency_digest = canonical_sha256({"dependencies": []})
    schema_digest = _file_sha256(ROOT / "contracts" / "tool-request.v0.1.schema.json")
    description_digest = canonical_sha256({"tool": "system.health", "metadata": metadata})
    topology = {
        "controller_location": "LOCAL_ETB_HARNESS_PROCESS",
        "tool_execution_location": "LOCAL_AIOS_TOOLS_SHARED_CORE",
        "filesystem_boundary": "REPOSITORY_READ_ONLY_CONFIGURATION",
        "shell_boundary": "NONE",
        "credential_audience": "NONE",
        "network_class": "NO_EXTERNAL_EFFECT",
        "orchestration_owner": "AIOS_TOOLS_EXPERIMENTAL_HARNESS",
        "inference_location": "NONE",
        "worker_identity": "PYTHON_PROCESS_LOCAL",
        "data_egress_policy_id": "NO_EGRESS",
    }
    return {
        "schema": SCHEMA_ID,
        "execution_id": "etb-real-system-health-01",
        "scope_key": "global-working-memory",
        "capability_id": "cap:aios-tools-health",
        "principal_id": "service:etb-harness",
        "asset_or_tool_identity": {
            "kind": "TOOL",
            "stable_id": "system.health",
            "version_label": metadata["version"],
            "content_digest": tool_digest,
            "expected_content_digest": tool_digest,
            "dependency_manifest_digest": dependency_digest,
            "expected_dependency_manifest_digest": dependency_digest,
        },
        "catalog_state": {
            "catalog_revision": registry_version,
            "schema_digest": schema_digest,
            "expected_schema_digest": schema_digest,
            "description_digest": description_digest,
            "expected_description_digest": description_digest,
            "freshness": "FRESH",
            "discovered_state": "KNOWN",
        },
        "policy_state": {
            "policy_id": "execution-policy.v0.1",
            "policy_version": policy["policy_version"],
            "parameter_class": "EMPTY_OBJECT",
            "consent": "NOT_REQUIRED",
            "decision": "ALLOW",
        },
        "security_trust": {
            "scanner_or_validator_id": "repository-config-validation",
            "result": "NOT_APPLICABLE",
            "project_scope": "neohack2023/AIOS-Tools",
        },
        "runtime_topology": topology,
        "extension_binding": {
            "extension_id": None,
            "resolved_revision": None,
            "manifest_digest": None,
            "backend_scope": None,
            "browser_context_isolation": "UNKNOWN",
            "enablement_state": "DISABLED",
        },
        "producer_lineage": {
            "producer_execution_id": None,
            "source_receipt_ids": [],
        },
        "semantic_authority": {
            "authority_class": "EXECUTION_EVIDENCE_ONLY",
            "destination_scope": "global-working-memory/research",
            "canon_or_trusted_promotion_allowed": False,
        },
        "requested_operation": {
            "action": "EXECUTE_READ_ONLY",
            "mode": "READ_ONLY",
            "effect_class": "NO_EXTERNAL_EFFECT",
            "artifact_upload": False,
            "semantic_promotion": False,
            "skill_installation": False,
            "authenticated_requests": 0,
        },
        "artifact_dependencies": [],
        "runtime_observation": {
            "topology": copy.deepcopy(topology),
            "egress_enabled": False,
            "authenticated_request_count": 0,
        },
        "skill_compounding": {
            "recurrence_nominated": False,
            "held_out_validation": "NOT_RUN",
            "install_authorized": False,
        },
        "invalidation_events": [],
    }


def build_runtime_system_health_binding(
    *,
    request_id: str,
    scope_key: str,
    requested_by: dict[str, Any],
    activation: dict[str, Any],
) -> dict[str, Any]:
    """Bind the live system.health implementation to policy-pinned identity.

    The observed digests come from the runtime. Expected digests come only
    from the active execution policy, so same-version code or schema drift
    fails closed instead of blessing itself at runtime.
    """

    binding = build_system_health_binding()
    pins = activation["bindings"]["system.health"]
    requester_type = requested_by.get("type", "UNKNOWN")
    requester_id = requested_by.get("id", "UNKNOWN")
    binding["execution_id"] = f"trust:{request_id}"
    binding["scope_key"] = scope_key
    binding["principal_id"] = f"{str(requester_type).lower()}:{requester_id}"
    identity = binding["asset_or_tool_identity"]
    identity["expected_content_digest"] = pins["content_digest"]
    identity["expected_dependency_manifest_digest"] = pins[
        "dependency_manifest_digest"
    ]
    catalog = binding["catalog_state"]
    catalog["expected_schema_digest"] = pins["request_schema_digest"]
    catalog["expected_description_digest"] = pins["description_digest"]
    if identity["version_label"] != pins["tool_version"]:
        binding["invalidation_events"].append("tool.catalog.changed")
    return binding


def admit_and_invoke_read_only(
    binding: dict[str, Any],
    tool: str,
    payload: dict[str, Any],
    *,
    executor: Callable[..., dict[str, Any]] | None = None,
) -> dict[str, Any]:
    if executor is None:
        # Imported lazily so the production runner can depend on the trust
        # evaluator without creating a module cycle.
        from .runner import invoke

        executor = invoke
    trust_receipt = evaluate_trust_binding(binding)
    gate_errors: list[str] = []
    if binding.get("asset_or_tool_identity", {}).get("stable_id") != tool:
        gate_errors.append("BOUND_TOOL_ID_MISMATCH")
    if binding.get("requested_operation", {}).get("mode") != "READ_ONLY":
        gate_errors.append("REAL_PATH_NOT_READ_ONLY")

    if not gate_errors and trust_receipt["admitted"]:
        registry, registry_version = load_registry(HANDLERS)
        policy = load_policy()
        metadata = registry.get(tool)
        if metadata is None:
            gate_errors.append("BOUND_TOOL_REMOVED")
        else:
            if metadata["version"] != binding["asset_or_tool_identity"]["version_label"]:
                gate_errors.append("BOUND_TOOL_VERSION_STALE")
            if registry_version != binding["catalog_state"]["catalog_revision"]:
                gate_errors.append("BOUND_CATALOG_REVISION_STALE")
            if policy["policy_version"] != binding["policy_state"]["policy_version"]:
                gate_errors.append("BOUND_POLICY_VERSION_STALE")
            if metadata["mode"] != "READ_ONLY":
                gate_errors.append("CURRENT_TOOL_NOT_READ_ONLY")
            if metadata["effect_class"] != binding["requested_operation"]["effect_class"]:
                gate_errors.append("BOUND_EFFECT_CLASS_STALE")
            current_tool_digest = _tool_content_digest(metadata, HANDLERS[tool])
            if current_tool_digest != binding["asset_or_tool_identity"]["content_digest"]:
                gate_errors.append("BOUND_TOOL_CONTENT_STALE")
            current_schema_digest = _file_sha256(
                ROOT / "contracts" / "tool-request.v0.1.schema.json"
            )
            if current_schema_digest != binding["catalog_state"]["schema_digest"]:
                gate_errors.append("BOUND_REQUEST_SCHEMA_STALE")
            current_description_digest = canonical_sha256(
                {"tool": tool, "metadata": metadata}
            )
            if current_description_digest != binding["catalog_state"]["description_digest"]:
                gate_errors.append("BOUND_TOOL_DESCRIPTION_STALE")

    if not trust_receipt["admitted"] or gate_errors:
        return {
            "schema": "aios.execution-trust-bound-path.v0.1",
            "path_status": "BLOCKED",
            "executor_invoked": False,
            "gate_errors": gate_errors,
            "trust_receipt": trust_receipt,
            "tool_receipt": None,
            "authority_transfer": False,
        }

    tool_receipt = executor(
        tool,
        payload,
        request_id=f"{binding['execution_id']}-tool",
        scope=binding["scope_key"],
        mode="READ_ONLY",
        requested_by={"type": "SERVICE", "id": "etb-harness"},
        authority_context={
            "trust_binding_receipt_id": trust_receipt["trust_receipt_id"],
            "governing_contract": CONTRACT_ID,
            "semantic_promotion_allowed": False,
        },
        provenance=[
            {
                "source": "AIOS_EXECUTION_TRUST_BINDING_01",
                "role": "GOVERNING_CONTRACT",
            }
        ],
    )
    completed_safely = (
        tool_receipt.get("status") == "COMPLETED"
        and tool_receipt.get("mode") == "READ_ONLY"
        and tool_receipt.get("external_effects") == []
        and tool_receipt.get("authority_transfer") is False
    )
    return {
        "schema": "aios.execution-trust-bound-path.v0.1",
        "path_status": "COMPLETED" if completed_safely else "TOOL_FAILED_OR_EFFECTFUL",
        "executor_invoked": True,
        "gate_errors": [],
        "trust_receipt": trust_receipt,
        "tool_receipt": tool_receipt,
        "authority_transfer": False,
    }
