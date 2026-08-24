from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from aios_tools.browser.keyring_store import KeyringProtectedSessionStore
from aios_tools.browser.secret_store import ProtectedBackendUnavailable
from aios_tools.browser.session import AuthCapabilityManifest, SessionDescriptor, SessionLifecycle, identity_fingerprint


class AdmittedBackend:
    priority = 1


AdmittedBackend.__module__ = "keyring.backends.Windows"


class RejectedBackend:
    priority = 1


RejectedBackend.__module__ = "unsafe.plaintext"


class FakeKeyring:
    def __init__(self, backend):
        self.backend = backend
        self.values = {}

    def get_keyring(self):
        return self.backend

    def set_password(self, service, user, value):
        self.values[(service, user)] = value

    def get_password(self, service, user):
        return self.values.get((service, user))

    def delete_password(self, service, user):
        self.values.pop((service, user), None)


def _descriptor(store):
    now = datetime.now(timezone.utc)
    return SessionDescriptor.verified(
        origin="https://example.com",
        identity_context_fingerprint=identity_fingerprint("test-user"),
        created_at=now,
        verified_at=now,
        expires_at=now + timedelta(hours=1),
        backend_kind=store.backend_kind,
        capabilities=AuthCapabilityManifest(cookies=True),
    )


def test_keyring_store_roundtrip_and_terminal_secret_purge():
    module = FakeKeyring(AdmittedBackend())
    store = KeyringProtectedSessionStore(
        allowed_backend_prefixes=("keyring.backends.Windows.",),
        keyring_module=module,
        service_name="AIOS-Test",
    )
    assert store.health().usable is True
    descriptor = _descriptor(store)
    store.put_sealed(descriptor.session_ref, b'{"cookies":[]}', descriptor)
    assert store.open_sealed(descriptor.session_ref) == b'{"cookies":[]}'
    assert store.metadata(descriptor.session_ref).origin == "https://example.com"
    assert store.mark_lifecycle(descriptor.session_ref, SessionLifecycle.REVOKED) is True
    with pytest.raises(Exception):
        store.open_sealed(descriptor.session_ref)


def test_keyring_store_rejects_unadmitted_backend():
    store = KeyringProtectedSessionStore(
        allowed_backend_prefixes=("keyring.backends.Windows.",),
        keyring_module=FakeKeyring(RejectedBackend()),
    )
    assert store.health().usable is False
    with pytest.raises(ProtectedBackendUnavailable):
        store.metadata(_descriptor(
            KeyringProtectedSessionStore(
                allowed_backend_prefixes=("keyring.backends.Windows.",),
                keyring_module=FakeKeyring(AdmittedBackend()),
            )
        ).session_ref)
