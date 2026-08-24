from __future__ import annotations

import asyncio
from datetime import datetime, timedelta, timezone
from hashlib import sha256
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import threading

import pytest

pytest.importorskip("playwright")

from aios_tools.browser.secret_store import InMemorySyntheticProtectedSessionStore
from aios_tools.browser.session import identity_fingerprint
from aios_tools.browser.session_capture import (
    SessionCapturePolicyError,
    build_session_capture_grant,
    capture_session_async,
)


class _Handler(BaseHTTPRequestHandler):
    def log_message(self, format, *args):
        return

    def do_GET(self):
        if self.path == "/login":
            body = b"""<!doctype html><html><body>
<form method="post" action="/login">
<button type="submit">Sign in</button>
</form></body></html>"""
            self.send_response(200)
            self.send_header("Content-Type", "text/html")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return
        if self.path == "/account":
            body = b"""<!doctype html><html><body>
<div data-testid="logged-in">Authenticated fixture</div>
</body></html>"""
            self.send_response(200)
            self.send_header("Content-Type", "text/html")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return
        self.send_response(404)
        self.end_headers()

    def do_POST(self):
        if self.path != "/login":
            self.send_response(404)
            self.end_headers()
            return
        self.send_response(303)
        self.send_header("Location", "/account")
        self.send_header("Set-Cookie", "session=fixture-only; Path=/; HttpOnly; SameSite=Lax")
        self.end_headers()


class _Server:
    def __init__(self):
        self.httpd = ThreadingHTTPServer(("127.0.0.1", 0), _Handler)
        self.thread = threading.Thread(target=self.httpd.serve_forever, daemon=True)

    @property
    def origin(self):
        host, port = self.httpd.server_address
        return f"http://{host}:{port}"

    def __enter__(self):
        self.thread.start()
        return self

    def __exit__(self, *args):
        self.httpd.shutdown()
        self.httpd.server_close()
        self.thread.join(timeout=2)


def _transition_digest(origins):
    encoded = json.dumps(tuple(sorted(origins)), separators=(",", ":")).encode()
    return "sha256:" + sha256(encoded).hexdigest()


def _approved_payload(origin):
    identity = identity_fingerprint("fixture-user")
    now = datetime.now(timezone.utc)
    payload = {
        "url": origin + "/login",
        "identity_context_fingerprint": identity,
        "capture_key": "capture-fixture-1",
        "explicit_transition_origins": [],
        "verification_locator": {
            "kind": "test_id",
            "value": "logged-in",
            "exact": True,
        },
        "takeover_timeout_seconds": 30,
        "session_ttl_seconds": 3600,
    }
    authority = {
        "approval": {
            "approved": True,
            "approved_by": "fixture-operator",
            "approval_id": "approval-capture-1",
            "tool": "browser.session.capture",
            "scope": "global-working-memory",
            "effect_class": "REMOTE_MUTATION_HIGH_IMPACT",
            "target_origin": origin,
            "identity_context_fingerprint": identity,
            "transition_origins_fingerprint": _transition_digest(()),
            "capture_key": "capture-fixture-1",
            "one_shot": True,
            "high_impact_ack": True,
            "expires_at": (now + timedelta(minutes=5)).isoformat(),
        }
    }
    grant = build_session_capture_grant(
        request_id="request-capture-1",
        tool="browser.session.capture",
        scope="global-working-memory",
        effect_class="REMOTE_MUTATION_HIGH_IMPACT",
        payload=payload,
        authority_context=authority,
        now=now,
    )
    payload["_aios_session_capture_grant"] = grant
    return payload


def test_session_capture_requires_exact_approval():
    identity = identity_fingerprint("fixture-user")
    with pytest.raises(SessionCapturePolicyError) as exc:
        build_session_capture_grant(
            request_id="request-x",
            tool="browser.session.capture",
            scope="global-working-memory",
            effect_class="REMOTE_MUTATION_HIGH_IMPACT",
            payload={
                "url": "https://example.com/login",
                "identity_context_fingerprint": identity,
                "capture_key": "capture-x",
                "explicit_transition_origins": [],
            },
            authority_context={},
        )
    assert exc.value.code == "APPROVAL_REQUIRED"


def test_session_capture_human_control_path_seals_state_without_raw_ref():
    with _Server() as server:
        payload = _approved_payload(server.origin)
        store = InMemorySyntheticProtectedSessionStore(synthetic_test_mode=True)

        async def user_action(page):
            await page.get_by_role("button", name="Sign in", exact=True).click()

        result = asyncio.run(
            capture_session_async(
                payload,
                store=store,
                allow_private_fixture=True,
                headless_fixture=True,
                fixture_user_action=user_action,
            )
        )
        assert result["terminal_status"] == "SESSION_AVAILABLE"
        assert result["semantic_success"] is True
        assert result["mutation_count"] == 1
        assert result["method"] == "AUTH_FLOW"
        assert result["raw_session_ref_exposed"] is False
        rendered = json.dumps(result, sort_keys=True)
        assert "fixture-only" not in rendered
        assert '"session_ref":' not in rendered
        assert result["session"]["capabilities"]["cookies"] is True
        assert len(store._records) == 1
