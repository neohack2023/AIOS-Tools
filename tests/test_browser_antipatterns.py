from pathlib import Path

from aios_tools.browser.models import SemanticLocator
from aios_tools.browser.policy import load_browser_policy

PACKAGE = Path(__file__).resolve().parents[1] / "src" / "aios_tools" / "browser"


def _browser_source() -> str:
    return "\n".join(path.read_text(encoding="utf-8") for path in sorted(PACKAGE.glob("*.py")))


def test_public_locator_contract_has_no_css_or_xpath_kind():
    for forbidden in ("css", "xpath", "selector"):
        try:
            SemanticLocator(kind=forbidden, value="x")
        except ValueError:
            pass
        else:
            raise AssertionError(f"{forbidden} locator unexpectedly admitted")


def test_harvested_browser_antipattern_primitives_are_absent():
    source = _browser_source()
    forbidden = [
        "force=True",
        "wait_for_timeout(",
        "networkidle",
        "locator.all(",
        "connect_over_cdp(",
        "launch_persistent_context(",
        ".evaluate(",
        "time.sleep(",
        "xpath=",
        "css=",
        "connect_to_server(",
        "await ws.connect(",
    ]
    for pattern in forbidden:
        assert pattern not in source, pattern


def test_storage_state_access_is_confined_to_protected_adapter():
    adapter = PACKAGE / "storage_state.py"
    assert adapter.exists()
    for path in sorted(PACKAGE.glob("*.py")):
        source = path.read_text(encoding="utf-8")
        if path == adapter:
            continue
        assert ".storage_state(" not in source, path.name
        assert "storage_state=" not in source, path.name

    source = adapter.read_text(encoding="utf-8")
    assert "context.storage_state(indexed_db=True, credentials=False)" in source
    assert "storage_state=state" in source
    assert "storage_state_path" not in source
    assert "path=" not in source
    assert "credentials=True" not in source


def test_required_network_guards_are_present():
    source = _browser_source()
    assert 'service_workers="block"' in source
    assert 'accept_downloads=False' in source
    assert 'route_web_socket("**/*"' in source
    assert 'context.route("**/*"' in source
    policy = load_browser_policy()
    assert policy["public_network_only"] is True
    assert policy["allowed_http_methods"] == ["GET", "HEAD"]
    assert policy["websocket_policy"] == "block"
    assert policy["downloads"] == "block"


def test_browser_payload_cannot_supply_authority_or_paths():
    runtime = (PACKAGE / "runtime.py").read_text(encoding="utf-8")
    assert '{"url", "visible_text_chars", "elapsed_seconds"}' in runtime
    for caller_controlled in ("output_dir", "trace_path", "storage_state", "origin_allowlist", "effect_class"):
        assert caller_controlled not in '{"url", "visible_text_chars", "elapsed_seconds"}'
