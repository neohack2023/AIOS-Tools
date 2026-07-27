import json
from pathlib import Path

from jsonschema import Draft202012Validator

from aios_tools import config
from aios_tools.canonical import canonical_sha256
from aios_tools.runner import invoke
from aios_tools.tools import HANDLERS


def test_canonical_hash_is_order_independent():
    assert canonical_sha256({"b": 2, "a": 1}) == canonical_sha256({"a": 1, "b": 2})


def test_health_receipt_is_read_only_independent_and_traced():
    receipt = invoke("system.health", {})
    assert receipt["status"] == "COMPLETED"
    assert receipt["mode"] == "READ_ONLY"
    assert receipt["authority_transfer"] is False
    assert receipt["external_effects"] == []
    assert receipt["output"]["portable_repo_required"] is False
    assert receipt["registry_version"] == "0.1.0"
    assert receipt["policy_version"] == "0.1.0"
    assert receipt["requested_by"] == {"type": "SERVICE", "id": "aios-tools-python"}
    assert receipt["output"]["policy"]["durable_writes_enabled"] is False
    assert receipt["output"]["policy"]["external_network_effects_enabled"] is False


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
    assert receipt["errors"][0]["code"] == "TOOL_NOT_REGISTERED"
    assert receipt["external_effects"] == []


def test_disallowed_mode_is_blocked_by_global_policy():
    receipt = invoke("system.health", {}, mode="WRITE")
    assert receipt["status"] == "BLOCKED"
    assert receipt["errors"][0]["code"] == "MODE_GLOBALLY_BLOCKED"
    assert receipt["external_effects"] == []
    assert receipt["authority_transfer"] is False


def test_invalid_requester_is_blocked_by_request_contract():
    receipt = invoke("system.health", {}, requested_by={"type": "ROBOT", "id": "x"})
    assert receipt["status"] == "BLOCKED"
    assert receipt["errors"][0]["code"] == "REQUEST_INVALID"


def test_missing_or_malformed_policy_fails_closed(monkeypatch, tmp_path):
    bad_policy = tmp_path / "execution-policy.json"
    bad_policy.write_text("{}", encoding="utf-8")
    monkeypatch.setattr(config, "POLICY_PATH", bad_policy)
    receipt = invoke("system.health", {})
    assert receipt["status"] == "BLOCKED"
    assert receipt["errors"][0]["code"] == "CONFIGURATION_INVALID"


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
    assert receipt["errors"][0]["code"] == "INTERNAL_ERROR"
    assert "secret internal detail" not in receipt["errors"][0]["message"]


def test_result_contract_validates_completed_and_blocked_receipts():
    schema = json.loads(Path("contracts/tool-result.v0.1.schema.json").read_text())
    completed = invoke("system.health", {})
    blocked = invoke("system.health", {}, mode="WRITE")
    assert list(Draft202012Validator(schema).iter_errors(completed)) == []
    assert list(Draft202012Validator(schema).iter_errors(blocked)) == []
