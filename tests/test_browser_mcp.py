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


def test_mcp_interactive_session_adapters_route_to_shared_core(monkeypatch):
    observed = []

    def fake_invoke(tool, payload, *, scope, requested_by):
        observed.append((tool, payload, scope, requested_by))
        return {"status": "COMPLETED"}

    monkeypatch.setattr(mcp_server, "invoke", fake_invoke)
    opened = mcp_server.browser_session_open("https://example.com")
    acted = mcp_server.browser_session_act(
        "browser-session-" + "a" * 32,
        [{"type": "scroll", "delta_y": 500}],
    )
    closed = mcp_server.browser_session_close("browser-session-" + "a" * 32)
    assert opened == acted == closed == {"status": "COMPLETED"}
    assert [item[0] for item in observed] == [
        "browser.session.open",
        "browser.session.act",
        "browser.session.close",
    ]
    assert observed[0][1]["resource_origins"] == []
    assert observed[1][1]["actions"][0]["type"] == "scroll"


def test_mcp_remote_mutation_adapter_routes_write_authority_to_shared_core(monkeypatch):
    observed = {}

    def fake_invoke(tool, payload, *, scope, mode, requested_by, authority_context):
        observed.update(
            tool=tool,
            payload=payload,
            scope=scope,
            mode=mode,
            requested_by=requested_by,
            authority_context=authority_context,
        )
        return {"status": "COMPLETED"}

    monkeypatch.setattr(mcp_server, "invoke", fake_invoke)
    payload = {"url": "https://example.com/api", "method": "POST", "idempotency_key": "mcp-1"}
    authority = {"approval": {"approved": True}}
    result = mcp_server.browser_mutate_request(payload, authority)
    assert result == {"status": "COMPLETED"}
    assert observed["tool"] == "browser.mutate.request"
    assert observed["mode"] == "WRITE"
    assert observed["authority_context"] is authority


def test_mcp_session_capture_adapter_never_adds_secret_fields(monkeypatch):
    observed = {}

    def fake_invoke(tool, payload, *, scope, mode, requested_by, authority_context):
        observed.update(tool=tool, payload=payload, mode=mode, authority_context=authority_context)
        return {"status": "COMPLETED"}

    monkeypatch.setattr(mcp_server, "invoke", fake_invoke)
    payload = {
        "url": "https://example.com/login",
        "identity_context_fingerprint": "sha256:" + "a" * 64,
        "capture_key": "capture-mcp",
        "explicit_transition_origins": [],
        "verification_locator": {"kind": "test_id", "value": "signed-in"},
    }
    authority = {"approval": {"approved": True}}
    result = mcp_server.browser_session_capture(payload, authority)
    assert result == {"status": "COMPLETED"}
    assert observed["tool"] == "browser.session.capture"
    assert observed["mode"] == "WRITE"
    rendered = repr(observed)
    for forbidden in ("password", "mfa_code", "recovery_code", "private_key"):
        assert forbidden not in rendered
