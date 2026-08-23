import json
from pathlib import Path

from jsonschema import Draft202012Validator

from aios_tools.runner import _browser_external_effects, _receipt


def test_browser_receipt_reports_minimized_observed_network_effect():
    output = {
        "target_origin": "https://example.com",
        "terminal_status": "SUCCEEDED",
        "budget_used": {"websockets": 0},
        "evidence": {
            "network": [
                {"event": "request", "method": "GET", "origin": "https://example.com", "path_digest": "sha256:x"},
                {"event": "response", "origin": "https://example.com", "path_digest": "sha256:x", "status": 200},
            ],
            "blocked": [],
        },
    }
    effects = _browser_external_effects("browser.inspect", "READ_NETWORK", output)
    assert effects == [{
        "effect_class": "READ_NETWORK",
        "capability_id": "cap:browser-control",
        "target_origin": "https://example.com",
        "request_count": 1,
        "websocket_count": 0,
        "terminal_status": "SUCCEEDED",
    }]
    serialized = json.dumps(effects)
    for secret_shape in ("query", "headers", "cookies", "body", "authorization", "/private/path"):
        assert secret_shape not in serialized.lower()


def test_non_network_receipt_still_requires_zero_external_effects():
    receipt = _receipt(
        request_id="r",
        tool="system.health",
        tool_version="0.1.0",
        scope="global-working-memory",
        mode="READ_ONLY",
        effect_class="NO_EXTERNAL_EFFECT",
        status="COMPLETED",
        started_at="2026-08-23T00:00:00+00:00",
        handler_invoked=True,
    )
    assert receipt["external_effects"] == []
    schema = json.loads(Path("contracts/tool-result.v0.1.schema.json").read_text(encoding="utf-8"))
    assert list(Draft202012Validator(schema).iter_errors(receipt)) == []


def test_browser_network_receipt_shape_validates():
    receipt = _receipt(
        request_id="r",
        tool="browser.inspect",
        tool_version="0.1.0",
        scope="global-working-memory",
        mode="READ_ONLY",
        effect_class="READ_NETWORK",
        status="COMPLETED",
        started_at="2026-08-23T00:00:00+00:00",
        handler_invoked=True,
        external_effects=[{
            "effect_class": "READ_NETWORK",
            "capability_id": "cap:browser-control",
            "target_origin": "https://example.com",
            "request_count": 1,
            "websocket_count": 0,
            "terminal_status": "SUCCEEDED",
        }],
    )
    schema = json.loads(Path("contracts/tool-result.v0.1.schema.json").read_text(encoding="utf-8"))
    assert list(Draft202012Validator(schema).iter_errors(receipt)) == []
