import json
import tomllib
from pathlib import Path

import aios_tools.browser_mcp_server as browser_mcp_server


def test_browser_only_mcp_exposes_exact_session_surface():
    tools = {tool.name: tool for tool in browser_mcp_server.mcp._tool_manager.list_tools()}

    assert set(tools) == {
        "browser_session_open",
        "browser_session_observe",
        "browser_session_act",
        "browser_session_close",
    }
    for name in ("browser_session_open", "browser_session_observe", "browser_session_act"):
        assert tools[name].annotations.readOnlyHint is True
        assert tools[name].annotations.destructiveHint is False
        assert tools[name].annotations.openWorldHint is True
    assert tools["browser_session_close"].annotations.readOnlyHint is True
    assert tools["browser_session_close"].annotations.destructiveHint is False
    assert tools["browser_session_close"].annotations.openWorldHint is False


def test_browser_only_mcp_routes_all_calls_to_shared_core(monkeypatch):
    observed = []

    def fake_invoke(tool, payload, *, scope, requested_by):
        observed.append((tool, payload, scope, requested_by))
        return {"status": "COMPLETED"}

    monkeypatch.setattr(browser_mcp_server, "invoke", fake_invoke)
    session_id = "browser-session-" + "a" * 32

    assert browser_mcp_server.browser_session_open("https://example.com") == {"status": "COMPLETED"}
    assert browser_mcp_server.browser_session_observe(session_id) == {"status": "COMPLETED"}
    assert browser_mcp_server.browser_session_act(
        session_id,
        [{"type": "scroll", "delta_y": 500}],
    ) == {"status": "COMPLETED"}
    assert browser_mcp_server.browser_session_close(session_id) == {"status": "COMPLETED"}

    assert [item[0] for item in observed] == [
        "browser.session.open",
        "browser.session.observe",
        "browser.session.act",
        "browser.session.close",
    ]
    assert all(item[2] == "global-working-memory" for item in observed)
    assert all(item[3] == {"type": "LLM", "id": "aios-browser-mcp"} for item in observed)


def test_browser_only_mcp_deployment_config_is_explicit():
    config = json.loads(Path("alpic.json").read_text(encoding="utf-8"))
    project = tomllib.loads(Path("pyproject.toml").read_text(encoding="utf-8"))

    assert config["startCommand"] == "uv run aios-browser-mcp-alpic"
    assert "uv sync --extra browser" in config["installCommand"]
    assert "playwright install chromium" in config["installCommand"]
    assert (
        project["project"]["scripts"]["aios-browser-mcp-alpic"]
        == "aios_tools.browser_mcp_server:alpic_main"
    )


def test_browser_only_server_instructions_keep_untrusted_boundary_visible():
    instructions = browser_mcp_server.SERVER_INSTRUCTIONS
    assert len(instructions) <= 512
    assert "untrusted" in instructions
    assert "read-only" in instructions
    assert "browser_session_close" in instructions
