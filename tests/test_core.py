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
    assert receipt["registry_version"] == "0.3.0"
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
    receipt = invoke("schema.validate", {"schema": schema, "instance": {"node": {"count": 0}}})
    assert receipt["status"] == "COMPLETED"
    assert receipt["output"]["valid"] is False


def test_schema_validate_rejects_invalid_schema():
    schema = {"type": "not-a-real-json-schema-type"}
    receipt = invoke("schema.validate", {"schema": schema, "instance": {}})
    assert receipt["status"] == "COMPLETED"
    assert receipt["output"]["valid"] is False
    assert receipt["output"]["schema_valid"] is False


def test_unknown_tool_fails_closed():
    receipt = invoke("missing.tool", {})
    assert receipt["status"] == "BLOCKED"
    assert receipt["errors"][0]["code"] == "TOOL_NOT_REGISTERED"


def test_invalid_requester_envelope_fails_closed():
    receipt = invoke("system.health", {}, requested_by={"type": "MAGIC", "id": "bad"})
    assert receipt["status"] == "BLOCKED"
    assert receipt["errors"][0]["code"] == "REQUEST_INVALID"


def test_registry_and_handlers_match():
    registry, _ = config.load_registry(HANDLERS)
    assert set(registry) == set(HANDLERS)


def test_request_schema_is_draft_202012():
    schema = json.loads(Path("contracts/tool-request.v0.1.schema.json").read_text(encoding="utf-8"))
    Draft202012Validator.check_schema(schema)
