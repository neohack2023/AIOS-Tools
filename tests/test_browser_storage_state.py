from __future__ import annotations

import asyncio
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import inspect

import pytest

pytest.importorskip("playwright.async_api")
from playwright.async_api import async_playwright

from aios_tools.browser.auth import SessionValidator
from aios_tools.browser.secret_store import InMemorySyntheticProtectedSessionStore, UnavailableProtectedSessionStore
from aios_tools.browser.session import (
    AuthCapabilityManifest,
    SessionDescriptor,
    SessionLeaseRegistry,
    SessionValidationError,
    identity_fingerprint,
)
from aios_tools.browser.storage_state import (
    StorageStateSealer,
    classify_storage_state,
    validate_storage_state_scope,
)


IDENTITY = identity_fingerprint("synthetic-user@example.invalid")


class _FixtureHandler(BaseHTTPRequestHandler):
    def log_message(self, format, *args):
        return

    def do_GET(self):
        body = b"<html><body>storage fixture</body></html>"
        self.send_response(200)
        self.send_header("Content-Type", "text/html")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


@contextmanager
def fixture_server():
    server = ThreadingHTTPServer(("127.0.0.1", 0), _FixtureHandler)
    thread = __import__("threading").Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield server
    finally:
        server.shutdown()
        thread.join(timeout=5)
        server.server_close()


def _origin(server) -> str:
    return f"http://127.0.0.1:{server.server_address[1]}"


def _descriptor(origin: str, backend_kind: str) -> SessionDescriptor:
    now = datetime.now(timezone.utc)
    return SessionDescriptor.verified(
        origin=origin,
        identity_context_fingerprint=IDENTITY,
        created_at=now,
        verified_at=now,
        expires_at=now + timedelta(minutes=20),
        backend_kind=backend_kind,
        capabilities=AuthCapabilityManifest(),
    )


def test_storage_state_sealer_api_accepts_no_path_or_raw_secret_parameter():
    capture = set(inspect.signature(StorageStateSealer.capture_context).parameters)
    restore = set(inspect.signature(StorageStateSealer.restore_new_context).parameters)
    forbidden = {
        "path",
        "storage_state_path",
        "user_data_dir",
        "profile_path",
        "cookie",
        "cookies",
        "token",
        "password",
        "mfa_code",
        "credentials",
    }
    assert forbidden.isdisjoint(capture)
    assert forbidden.isdisjoint(restore)


def test_storage_state_classifies_cookie_localstorage_and_indexeddb():
    state = {
        "cookies": [{"name": "sid", "value": "synthetic", "domain": "example.invalid", "path": "/"}],
        "origins": [
            {
                "origin": "https://example.invalid",
                "localStorage": [{"name": "k", "value": "v"}],
                "indexedDB": [{"name": "db", "version": 1, "stores": []}],
            }
        ],
    }
    manifest = classify_storage_state(state)
    assert manifest.cookies is True
    assert manifest.local_storage is True
    assert manifest.indexed_db is True
    assert manifest.session_storage is False
    assert manifest.virtual_webauthn is False


def test_virtual_webauthn_credentials_are_rejected():
    descriptor = _descriptor("https://example.invalid", "synthetic-memory-test")
    state = {"cookies": [], "origins": [], "credentials": [{"credentialId": "fixture", "privateKey": "never"}]}
    with pytest.raises(SessionValidationError) as exc:
        validate_storage_state_scope(state, descriptor)
    assert exc.value.code == "VIRTUAL_WEBAUTHN_NOT_ADMITTED"


def test_sessionstorage_requires_separate_adapter():
    descriptor = _descriptor("https://example.invalid", "synthetic-memory-test")
    state = {
        "cookies": [],
        "origins": [{"origin": "https://example.invalid", "localStorage": [], "sessionStorage": [{"name": "x", "value": "y"}]}],
    }
    with pytest.raises(SessionValidationError) as exc:
        validate_storage_state_scope(state, descriptor)
    assert exc.value.code == "SESSION_STORAGE_ADAPTER_REQUIRED"


def test_cross_origin_storage_is_rejected():
    descriptor = _descriptor("https://example.invalid", "synthetic-memory-test")
    state = {
        "cookies": [],
        "origins": [{"origin": "https://other.invalid", "localStorage": [{"name": "k", "value": "v"}]}],
    }
    with pytest.raises(SessionValidationError) as exc:
        validate_storage_state_scope(state, descriptor)
    assert exc.value.code == "AUTH_STORAGE_ORIGIN_MISMATCH"


def test_cross_host_cookie_is_rejected():
    descriptor = _descriptor("https://example.invalid", "synthetic-memory-test")
    state = {
        "cookies": [{"name": "sid", "value": "synthetic", "domain": ".other.invalid", "path": "/"}],
        "origins": [],
    }
    with pytest.raises(SessionValidationError) as exc:
        validate_storage_state_scope(state, descriptor)
    assert exc.value.code == "AUTH_STORAGE_COOKIE_SCOPE_MISMATCH"


def test_capture_fails_closed_when_protected_backend_is_unavailable():
    class Context:
        async def storage_state(self, **kwargs):
            raise AssertionError("storage_state must not be opened when protected backend is unavailable")

    descriptor = _descriptor("https://example.invalid", "none")
    sealer = StorageStateSealer(UnavailableProtectedSessionStore())

    async def run():
        with pytest.raises(SessionValidationError) as exc:
            await sealer.capture_context(Context(), descriptor)
        assert exc.value.code == "PROTECTED_BACKEND_UNAVAILABLE"

    asyncio.run(run())


def test_capture_requests_indexeddb_but_explicitly_excludes_credentials():
    observed = {}

    class Context:
        async def storage_state(self, **kwargs):
            observed.update(kwargs)
            return {"cookies": [], "origins": []}

    store = InMemorySyntheticProtectedSessionStore(synthetic_test_mode=True)
    descriptor = _descriptor("https://example.invalid", store.BACKEND_KIND)
    sealer = StorageStateSealer(store)
    updated = asyncio.run(sealer.capture_context(Context(), descriptor))
    assert observed == {"indexed_db": True, "credentials": False}
    assert updated.capabilities.names() == frozenset()


def test_playwright_storage_state_round_trip_stays_behind_opaque_ref():
    async def run():
        with fixture_server() as server:
            origin = _origin(server)
            store = InMemorySyntheticProtectedSessionStore(synthetic_test_mode=True)
            descriptor = _descriptor(origin, store.BACKEND_KIND)
            sealer = StorageStateSealer(store)
            validator = SessionValidator(
                store=store,
                leases=SessionLeaseRegistry(),
                allow_synthetic_backend=True,
            )

            async with async_playwright() as pw:
                browser = await pw.chromium.launch(headless=True)
                source = await browser.new_context(service_workers="block", accept_downloads=False)
                page = await source.new_page()
                await page.goto(origin)
                await page.evaluate(
                    """async () => {
                        localStorage.setItem('aios_local', 'LOCAL_OK');
                        document.cookie = 'aios_cookie=COOKIE_OK; path=/';
                        await new Promise((resolve, reject) => {
                            const open = indexedDB.open('aios-db', 1);
                            open.onupgradeneeded = () => open.result.createObjectStore('kv');
                            open.onerror = () => reject(open.error);
                            open.onsuccess = () => {
                                const tx = open.result.transaction('kv', 'readwrite');
                                tx.objectStore('kv').put('INDEXED_OK', 'key');
                                tx.oncomplete = resolve;
                                tx.onerror = () => reject(tx.error);
                            };
                        });
                    }"""
                )

                updated = await sealer.capture_context(source, descriptor)
                await source.close()
                assert updated.capabilities.cookies is True
                assert updated.capabilities.local_storage is True
                assert updated.capabilities.indexed_db is True
                assert updated.capabilities.virtual_webauthn is False

                validated = validator.validate_for_restore(
                    updated.session_ref,
                    target_url=origin,
                    identity_context_fingerprint=IDENTITY,
                    owner_execution_id="fixture-exec",
                    lease_ttl_seconds=30,
                    required_capabilities=("cookies", "local_storage", "indexed_db"),
                )
                restored = await sealer.restore_new_context(browser, validated, validator)
                restored_page = await restored.new_page()
                await restored_page.goto(origin)
                local_value = await restored_page.evaluate("localStorage.getItem('aios_local')")
                cookie_value = await restored_page.evaluate("document.cookie")
                indexed_value = await restored_page.evaluate(
                    """async () => await new Promise((resolve, reject) => {
                        const open = indexedDB.open('aios-db', 1);
                        open.onerror = () => reject(open.error);
                        open.onsuccess = () => {
                            const tx = open.result.transaction('kv', 'readonly');
                            const get = tx.objectStore('kv').get('key');
                            get.onsuccess = () => resolve(get.result);
                            get.onerror = () => reject(get.error);
                        };
                    })"""
                )
                assert local_value == "LOCAL_OK"
                assert "aios_cookie=COOKIE_OK" in cookie_value
                assert indexed_value == "INDEXED_OK"
                await restored.close()
                assert validator.release(validated) is True
                await browser.close()

    asyncio.run(run())
