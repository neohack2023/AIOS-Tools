from __future__ import annotations

from aios_tools.runner import invoke
from aios_tools.browser.site_profile import load_site_profile


def test_browser_runtime_status_is_machine_readable_active():
    receipt = invoke("browser.runtime.status", {})
    assert receipt["status"] == "COMPLETED"
    output = receipt["output"]
    assert output["capability_id"] == "cap:browser-control"
    assert output["runtime_state"] == "ACTIVE"
    assert output["browser_policy_version"] == "browser-policy/1.1-candidate"
    assert output["auth_policy_version"] == "browser-auth-policy/1.0"
    assert output["session_reuse_enabled"] is True
    assert output["real_auth_state_capture_enabled"] is True
    assert output["production_user_takeover_enabled"] is True
    assert output["global_network_switch_changed"] is False
    assert output["authority_transfer"] is False
    assert {
        "browser.mutate.request",
        "browser.mutate.reversible",
        "browser.session.capture",
        "browser.upload.execute",
    }.issubset(set(output["remote_mutation_tools_admitted"]))


def test_first_production_profile_keeps_exact_suno_anchor():
    profile = load_site_profile("SITE_PROFILE_SUNO_TRACK_HARVEST_01")
    assert profile["origin"] == "https://suno.com"
    assert profile["validation_entrypoint"] == (
        "https://suno.com/song/1b63dccf-443f-43ce-a6dc-11034a94c5f9"
    )
    assert profile["mode"] == "REPLAY"
    assert profile["effect_class"] == "READ_NETWORK"
    assert profile["authority_transfer"] is False
