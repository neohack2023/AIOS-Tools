import aios_tools.mcp_server as mcp_server


def test_mcp_browser_adapter_routes_to_shared_core(monkeypatch):
    observed = {}

    def fake_invoke(tool, payload, *, scope, requested_by):
        observed.update(tool=tool, payload=payload, scope=scope, requested_by=requested_by)
        return {"status": "COMPLETED"}

    monkeypatch.setattr(mcp_server, "invoke", fake_invoke)
    result = mcp_server.browser_inspect(
        "https://example.com",
        visible_text_chars=123,
        elapsed_seconds=9,
        scope="global-working-memory",
    )
    assert result == {"status": "COMPLETED"}
    assert observed["tool"] == "browser.inspect"
    assert observed["payload"] == {
        "url": "https://example.com",
        "visible_text_chars": 123,
        "elapsed_seconds": 9,
    }
    assert observed["scope"] == "global-working-memory"
