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
