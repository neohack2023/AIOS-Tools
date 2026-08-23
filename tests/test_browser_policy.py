from copy import deepcopy

import aios_tools.browser.policy as browser_policy
import aios_tools.runner as runner
from aios_tools.config import load_policy
from aios_tools.tools import HANDLERS


def test_global_network_switch_stays_false():
    policy = load_policy()
    assert policy["external_network_effects_enabled"] is False
    assert "READ_NETWORK" not in policy["effect_policy"]["allowed_effect_classes"]


def test_browser_policy_is_exact_read_only_admission():
    policy = browser_policy.load_browser_policy()
    assert policy["effect_class"] == "READ_NETWORK"
    assert policy["admitted_tools"] == {
        "browser.inspect": {"mode": "READ_ONLY", "effect_class": "READ_NETWORK"}
    }
    assert policy["public_network_only"] is True
    assert policy["service_workers"] == "block"
    assert policy["websocket_policy"] == "same_origin_only"


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
