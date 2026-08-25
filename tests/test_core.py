import json
from pathlib import Path

from jsonschema import Draft202012Validator

from aios_tools import config
from aios_tools.canonical import canonical_sha256
from aios_tools.runner import invoke
from aios_tools.tools import HANDLERS


def _registry_document() -> dict:
    return json.loads(Path("registry/tools.v0.1.json").read_text(encoding="utf-8"))


def _policy_document() -> dict:
    return json.loads(Path("policies/execution-policy.v0.1.json").read_text(encoding="utf-8"))


def test_canonical_hash_is_order_independent():
    assert canonical_sha256({"b": 2, "a": 1}) == canonical_sha256({"a": 1, "b": 2})


def test_health_receipt_is_read_only_independent_and_traced():
    receipt = invoke("system.health", {})
    assert receipt["status"] == "COMPLETED"
    assert receipt["mode"] == "READ_ONLY"
    assert receipt["effect_class"] == "NO_EXTERNAL_EFFECT"
    assert receipt["authority_transfer"] is False
    assert receipt["external_effects"] == []
    assert receipt["output"]["portable_repo_required"] is False
    assert receipt["registry_version"] == "0.4.0"
    assert receipt["policy_version"] == "0.3.0-candidate"
    assert receipt["requested_by"] == {"type": "SERVICE", "id": "aios-tools-python"}
    assert receipt["output"]["policy"]["durable_writes_enabled"] is True
    assert receipt["output"]["policy"]["write_scope"] == "LOCAL_ARTIFACTS_ONLY"
    assert receipt["output"]["policy"]["external_network_effects_enabled"] is False
    assert receipt["output"]["policy"]["effect_policy"]["allowed_effect_classes"] == [
        "NO_EXTERNAL_EFFECT",
        "LOCAL_DURABLE_WRITE",
    ]


def test_schema_validate_accepts_valid_instance():
    schema = {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "type": "object",
        "required": ["name"],
        "properties": {"name": {"type": "string"}},
        "unevaluatedProperties": False,
    }
    receipt = invoke("schema.validate", {"schema": schema, "instance": {"name": "AIOS"}})
    assert receipt["status"] == "COMPLETED"
    assert receipt["effect_class"] == "NO_EXTERNAL_EFFECT"
    assert receipt["output"]["valid"] is True


def test_schema_validate_rejects_nested_invalid_instance():
    schema = {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "type": "object",
        "required": ["node"],
        "properties": {
            "node": {
                "type": "object",
                "required": ["count"],
                "properties": {"count": {"type": "integer", "minimum": 1}},
                "unevaluatedProperties": False,
            }
        },
        "unevaluatedProperties": False,
    }
    receipt = invoke("schema.validate", {"schema": schema, "instance": {"node": {"count": 0, "extra": True}}})
    assert receipt["status"] == "COMPLETED"
    assert receipt["output"]["valid"] is False
    validators = {error["validator"] for error in receipt["output"]["errors"]}
    assert "minimum" in validators
    assert "unevaluatedProperties" in validators


def test_unknown_tool_fails_closed():
    receipt = invoke("unknown.tool", {})
    assert receipt["status"] == "BLOCKED"
    assert receipt["effect_class"] == "UNKNOWN"
    assert receipt["errors"][0]["code"] == "TOOL_NOT_REGISTERED"
    assert receipt["external_effects"] == []


def test_globally_allowed_mode_still_respects_tool_mode():
    receipt = invoke("system.health", {}, mode="WRITE")
    assert receipt["status"] == "BLOCKED"
    assert receipt["errors"][0]["code"] == "MODE_NOT_ALLOWED"
    assert receipt["external_effects"] == []
    assert receipt["authority_transfer"] is False


def test_invalid_requester_is_blocked_by_request_contract():
    receipt = invoke("system.health", {}, requested_by={"type": "ROBOT", "id": "x"})
    assert receipt["status"] == "BLOCKED"
    assert receipt["effect_class"] == "NO_EXTERNAL_EFFECT"
    assert receipt["errors"][0]["code"] == "REQUEST_INVALID"


def test_missing_or_malformed_policy_fails_closed(monkeypatch, tmp_path):
    bad_policy = tmp_path / "execution-policy.json"
    bad_policy.write_text("{}", encoding="utf-8")
    monkeypatch.setattr(config, "POLICY_PATH", bad_policy)
    receipt = invoke("system.health", {})
    assert receipt["status"] == "BLOCKED"
    assert receipt["effect_class"] == "UNKNOWN"
    assert receipt["errors"][0]["code"] == "CONFIGURATION_INVALID"


def test_global_network_switch_remains_hard_disabled(monkeypatch, tmp_path):
    policy = _policy_document()
    policy["external_network_effects_enabled"] = True
    bad_policy = tmp_path / "execution-policy.json"
    bad_policy.write_text(json.dumps(policy), encoding="utf-8")
    monkeypatch.setattr(config, "POLICY_PATH", bad_policy)

    receipt = invoke("system.health", {})

    assert receipt["status"] == "BLOCKED"
    assert receipt["effect_class"] == "UNKNOWN"
    assert receipt["errors"][0]["code"] == "CONFIGURATION_INVALID"
    assert "external network effects must remain disabled" in receipt["errors"][0]["message"]


def test_policy_cannot_admit_network_class_while_global_network_is_disabled(monkeypatch, tmp_path):
    policy = _policy_document()
    policy["effect_policy"]["allowed_effect_classes"].append("READ_NETWORK")
    bad_policy = tmp_path / "execution-policy.json"
    bad_policy.write_text(json.dumps(policy), encoding="utf-8")
    monkeypatch.setattr(config, "POLICY_PATH", bad_policy)

    receipt = invoke("system.health", {})

    assert receipt["status"] == "BLOCKED"
    assert receipt["effect_class"] == "UNKNOWN"
    assert receipt["errors"][0]["code"] == "CONFIGURATION_INVALID"
    assert "network effect classes cannot be admitted" in receipt["errors"][0]["message"]


def test_registry_missing_effect_class_fails_closed(monkeypatch, tmp_path):
    registry = _registry_document()
    del registry["tools"][0]["effect_class"]
    bad_registry = tmp_path / "tools.json"
    bad_registry.write_text(json.dumps(registry), encoding="utf-8")
    monkeypatch.setattr(config, "REGISTRY_PATH", bad_registry)

    receipt = invoke("system.health", {})

    assert receipt["status"] == "BLOCKED"
    assert receipt["effect_class"] == "UNKNOWN"
    assert receipt["errors"][0]["code"] == "CONFIGURATION_INVALID"
    assert "effect_class" in receipt["errors"][0]["message"]


def test_registry_unknown_effect_class_fails_closed(monkeypatch, tmp_path):
    registry = _registry_document()
    registry["tools"][0]["effect_class"] = "MYSTERY_EFFECT"
    bad_registry = tmp_path / "tools.json"
    bad_registry.write_text(json.dumps(registry), encoding="utf-8")
    monkeypatch.setattr(config, "REGISTRY_PATH", bad_registry)

    receipt = invoke("system.health", {})

    assert receipt["status"] == "BLOCKED"
    assert receipt["effect_class"] == "UNKNOWN"
    assert receipt["errors"][0]["code"] == "CONFIGURATION_INVALID"
    assert "unknown effect_class" in receipt["errors"][0]["message"]


def test_network_effect_class_is_blocked_before_handler_invocation(monkeypatch, tmp_path):
    registry = _registry_document()
    registry["tools"][0]["effect_class"] = "READ_NETWORK"
    network_registry = tmp_path / "tools.json"
    network_registry.write_text(json.dumps(registry), encoding="utf-8")
    monkeypatch.setattr(config, "REGISTRY_PATH", network_registry)

    def should_never_run(_payload):
        raise AssertionError("blocked network handler was invoked")

    monkeypatch.setitem(HANDLERS, "system.health", should_never_run)
    receipt = invoke("system.health", {})

    assert receipt["status"] == "BLOCKED"
    assert receipt["effect_class"] == "READ_NETWORK"
    assert receipt["errors"][0]["code"] == "EXTERNAL_EFFECT_BLOCKED"
    assert receipt["external_effects"] == []
    event_types = [event["event_type"] for event in receipt["cognition_receipt"]["events"]]
    assert "tool.invoked" not in event_types


def test_registry_handler_drift_fails_closed(monkeypatch):
    handlers = dict(HANDLERS)
    handlers.pop("schema.validate")
    monkeypatch.setattr("aios_tools.runner.HANDLERS", handlers)
    receipt = invoke("system.health", {})
    assert receipt["status"] == "BLOCKED"
    assert receipt["errors"][0]["code"] == "CONFIGURATION_INVALID"
    assert "missing handlers" in receipt["errors"][0]["message"]


def test_unexpected_handler_exception_is_sanitized(monkeypatch):
    def explode(_payload):
        raise RuntimeError("secret internal detail")

    monkeypatch.setitem(HANDLERS, "system.health", explode)
    receipt = invoke("system.health", {})
    assert receipt["status"] == "FAILED"
    assert receipt["effect_class"] == "NO_EXTERNAL_EFFECT"
    assert receipt["errors"][0]["code"] == "INTERNAL_ERROR"
    assert "secret internal detail" not in receipt["errors"][0]["message"]


def test_result_contract_validates_completed_blocked_and_approval_receipts():
    schema = json.loads(Path("contracts/tool-result.v0.1.schema.json").read_text())
    completed = invoke("system.health", {})
    blocked = invoke("system.health", {}, mode="WRITE")
    approval_required = invoke(
        "audio.demucs.separate",
        {
            "source_path": "/does/not/matter/source.wav",
            "output_dir": "/does/not/matter/output",
            "profile_path": "/does/not/matter/profile.json",
        },
        mode="WRITE",
        scope="udio-algorithms",
    )
    assert list(Draft202012Validator(schema).iter_errors(completed)) == []
    assert list(Draft202012Validator(schema).iter_errors(blocked)) == []
    assert list(Draft202012Validator(schema).iter_errors(approval_required)) == []
