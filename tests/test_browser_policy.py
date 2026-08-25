from copy import deepcopy

import aios_tools.browser.policy as browser_policy
import aios_tools.runner as runner
from aios_tools.config import load_policy
from aios_tools.tools import HANDLERS


def test_global_network_switch_stays_false():
    policy = load_policy()
    assert policy["external_network_effects_enabled"] is False
    assert "READ_NETWORK" not in policy["effect_policy"]["allowed_effect_classes"]


def test_browser_policy_preserves_read_boundary_and_explicit_effect_admission():
    policy = browser_policy.load_browser_policy()
    assert policy["effect_class"] == "READ_NETWORK"
    assert policy["runtime_state"] == "ACTIVE"
    assert policy["policy_version"] == "browser-policy/1.0"
    assert policy["admitted_tools"]["browser.inspect"] == {
        "mode": "READ_ONLY",
        "effect_class": "READ_NETWORK",
    }
    assert policy["admitted_tools"]["browser.profile.replay"]["effect_class"] == "READ_NETWORK"
    assert policy["admitted_tools"]["browser.mutate.request"]["effect_class"] == "REMOTE_MUTATION_HIGH_IMPACT"
    assert policy["admitted_tools"]["browser.mutate.reversible"]["effect_class"] == "REMOTE_MUTATION_REVERSIBLE"
    assert policy["admitted_tools"]["browser.upload.execute"]["effect_class"] == "REMOTE_MUTATION_HIGH_IMPACT"
    assert policy["public_network_only"] is True
    assert policy["service_workers"] == "block"
    assert policy["websocket_policy"] == "block"
    assert policy["downloads"] == "block"
    assert policy["allowed_http_methods"] == ["GET", "HEAD"]
    assert policy["mutation_http_methods"] == ["POST", "PUT", "PATCH", "DELETE"]
    assert policy["mutation"]["ambiguous_state_retry"] is False
    assert policy["download_quarantine"]["status"] == "ACTIVE"
    assert policy["upload_intake"]["status"] == "ACTIVE"
    assert policy["mutation"]["status"] == "ACTIVE"


def test_unrelated_network_tool_never_reaches_handler(monkeypatch):
    called = False

    def forbidden_handler(payload):
        nonlocal called
        called = True
        raise AssertionError("network handler must never run")

    metadata = {
        "name": "synthetic.network.read",
        "version": "test",
        "mode": "READ_ONLY",
        "effect_class": "READ_NETWORK",
        "reversibility": "FULL",
        "blast_radius": "TEST",
        "authority_transfer": False,
    }
    policy = load_policy()
    monkeypatch.setattr(runner, "load_registry", lambda handlers: ({"synthetic.network.read": metadata}, "test"))
    monkeypatch.setattr(runner, "load_policy", lambda: deepcopy(policy))
    monkeypatch.setitem(HANDLERS, "synthetic.network.read", forbidden_handler)

    receipt = runner.invoke("synthetic.network.read", {})
    assert receipt["status"] == "BLOCKED"
    assert receipt["errors"][0]["code"] == "EXTERNAL_EFFECT_BLOCKED"
    assert called is False


def test_private_target_is_browser_block_not_internal_error():
    receipt = runner.invoke("browser.inspect", {"url": "http://127.0.0.1/"})
    assert receipt["errors"] == []
    assert receipt["output"]["terminal_status"] == "TARGET_BLOCKED"
    assert receipt["output"]["semantic_success"] is False
    assert receipt["output"]["evidence"]["blocked"]
