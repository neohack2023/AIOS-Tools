import json
from pathlib import Path

from jsonschema import Draft202012Validator

from aios_tools.canonical import canonical_sha256
from aios_tools.runner import invoke


def test_canonical_hash_is_order_independent():
    assert canonical_sha256({"b": 2, "a": 1}) == canonical_sha256({"a": 1, "b": 2})


def test_health_receipt_is_read_only_and_independent():
    receipt = invoke("system.health", {})
    assert receipt["status"] == "COMPLETED"
    assert receipt["mode"] == "READ_ONLY"
    assert receipt["authority_transfer"] is False
    assert receipt["external_effects"] == []
    assert receipt["output"]["portable_repo_required"] is False


def test_schema_validate_accepts_valid_instance():
    schema = {"$schema": "https://json-schema.org/draft/2020-12/schema", "type": "object", "required": ["name"], "properties": {"name": {"type": "string"}}, "unevaluatedProperties": False}
    receipt = invoke("schema.validate", {"schema": schema, "instance": {"name": "AIOS"}})
    assert receipt["status"] == "COMPLETED"
    assert receipt["output"]["valid"] is True


def test_schema_validate_rejects_nested_invalid_instance():
    schema = {"$schema": "https://json-schema.org/draft/2020-12/schema", "type": "object", "required": ["node"], "properties": {"node": {"type": "object", "required": ["count"], "properties": {"count": {"type": "integer", "minimum": 1}}, "unevaluatedProperties": False}}, "unevaluatedProperties": False}
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


def test_result_contract_validates_receipt():
    schema = json.loads(Path("contracts/tool-result.v0.1.schema.json").read_text())
    receipt = invoke("system.health", {})
    assert list(Draft202012Validator(schema).iter_errors(receipt)) == []
