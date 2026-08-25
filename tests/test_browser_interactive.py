from __future__ import annotations

from contextlib import contextmanager
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import threading

import pytest

pytest.importorskip("playwright.async_api")

from aios_tools.browser.interactive import InteractiveBrowserError, InteractiveBrowserService


class InteractiveFixtureHandler(BaseHTTPRequestHandler):
    post_seen: list[str] = []

    def log_message(self, format, *args):
        return

    def do_POST(self):
        type(self).post_seen.append(self.path)
        body = b"mutated"
        self.send_response(200)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        if self.path == "/start":
            body = b"""<html><head><title>Start</title></head><body>
            <a href='/next'>Next page</a>
            <input aria-label='Search' type='search'>
            <input aria-label='Password' type='password'>
            <button type='button' aria-label='Delete account'>Delete</button>
            <button type='button' aria-label='Details' onclick="fetch('/mutate',{method:'POST',body:'x'})">Details</button>
            </body></html>"""
        elif self.path == "/next":
            body = b"<html><head><title>Next</title></head><body>next body<a href='/start'>Return</a></body></html>"
        else:
            body = b"missing"
        self.send_response(200 if self.path in {"/start", "/next"} else 404)
        self.send_header("Content-Type", "text/html")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


@contextmanager
def fixture_server():
    InteractiveFixtureHandler.post_seen = []
    server = ThreadingHTTPServer(("127.0.0.1", 0), InteractiveFixtureHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield server
    finally:
        server.shutdown()
        thread.join(timeout=5)
        server.server_close()


def _url(server, path):
    return f"http://127.0.0.1:{server.server_address[1]}{path}"


def _ref(observation, name):
    return next(item["element_ref"] for item in observation["interactive_elements"] if item["name"] == name)


@pytest.fixture
def service():
    runtime = InteractiveBrowserService()
    try:
        yield runtime
    finally:
        runtime.shutdown()


def test_open_act_observe_close_preserves_one_opaque_session(service):
    with fixture_server() as server:
        opened = service.open({"url": _url(server, "/start")}, allow_private_fixture=True)
        assert opened["terminal_status"] == "SUCCEEDED"
        assert opened["session_id"].startswith("browser-session-")
        assert opened["observation"]["untrusted_page_data"] is True
        assert opened["observation"]["instruction_authority"] is False
        first_generation = opened["observation"]["observation_generation"]
        next_ref = _ref(opened["observation"], "Next page")

        acted = service.act({"session_id": opened["session_id"], "actions": [{"type": "click", "element_ref": next_ref}]})
        assert acted["terminal_status"] == "SUCCEEDED"
        assert acted["observation"]["title"] == "Next"
        assert acted["observation"]["observation_generation"] > first_generation
        assert "next body" in acted["observation"]["visible_text"]

        observed = service.observe({"session_id": opened["session_id"]})
        assert observed["terminal_status"] == "SUCCEEDED"
        assert observed["session_id"] == opened["session_id"]

        closed = service.close({"session_id": opened["session_id"]})
        assert closed["closed"] is True
        with pytest.raises(InteractiveBrowserError) as missing:
            service.observe({"session_id": opened["session_id"]})
        assert missing.value.code == "SESSION_NOT_FOUND"


def test_post_trigger_is_blocked_before_fixture_receives_mutation(service):
    with fixture_server() as server:
        opened = service.open({"url": _url(server, "/start")}, allow_private_fixture=True)
        ref = _ref(opened["observation"], "Details")
        result = service.act({"session_id": opened["session_id"], "actions": [{"type": "click", "element_ref": ref}]})
        assert result["terminal_status"] == "SESSION_BLOCKED"
        assert InteractiveFixtureHandler.post_seen == []
        assert any(item["reason"] == "HTTP_METHOD_NOT_ADMITTED" for item in result["evidence"]["blocked"])


def test_secret_and_high_risk_controls_are_blocked(service):
    with fixture_server() as server:
        opened = service.open({"url": _url(server, "/start")}, allow_private_fixture=True)
        password_ref = _ref(opened["observation"], "Password")
        secret = service.act({
            "session_id": opened["session_id"],
            "actions": [{"type": "fill", "element_ref": password_ref, "value": "never-record-this"}],
        })
        assert secret["terminal_status"] == "SECRET_FIELD_BLOCKED"
        assert "never-record-this" not in repr(secret)

        refreshed = service.observe({"session_id": opened["session_id"]})
        delete_ref = _ref(refreshed["observation"], "Delete account")
        risky = service.act({"session_id": opened["session_id"], "actions": [{"type": "click", "element_ref": delete_ref}]})
        assert risky["terminal_status"] == "ACTION_BLOCKED"


def test_old_element_reference_fails_after_new_observation(service):
    with fixture_server() as server:
        opened = service.open({"url": _url(server, "/start")}, allow_private_fixture=True)
        old_ref = _ref(opened["observation"], "Next page")
        service.observe({"session_id": opened["session_id"]})
        stale = service.act({"session_id": opened["session_id"], "actions": [{"type": "click", "element_ref": old_ref}]})
        assert stale["terminal_status"] == "ELEMENT_REF_STALE"


def test_cross_origin_navigation_is_rejected_before_action(service):
    with fixture_server() as server:
        opened = service.open({"url": _url(server, "/start")}, allow_private_fixture=True)
        result = service.act({
            "session_id": opened["session_id"],
            "actions": [{"type": "navigate", "url": "https://example.com/"}],
        })
        assert result["terminal_status"] == "ACTION_BLOCKED"
