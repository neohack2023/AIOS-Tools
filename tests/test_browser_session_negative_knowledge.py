from __future__ import annotations

from datetime import datetime, timedelta, timezone
import inspect

import pytest

from aios_tools.browser.auth import SessionValidator
from aios_tools.browser.secret_store import InMemorySyntheticProtectedSessionStore
from aios_tools.browser.session import (
    AuthCapabilityManifest,
    SessionDescriptor,
    SessionLeaseRegistry,
    identity_fingerprint,
)


def _descriptor(**overrides) -> SessionDescriptor:
    now = datetime(2026, 8, 23, 13, 0, tzinfo=timezone.utc)
    values = {
        "origin": "https://example.invalid",
        "identity_context_fingerprint": identity_fingerprint("synthetic-user@example.invalid"),
        "created_at": now,
        "verified_at": now,
        "expires_at": now + timedelta(hours=1),
        "backend_kind": InMemorySyntheticProtectedSessionStore.BACKEND_KIND,
        "capabilities": AuthCapabilityManifest(cookies=True, indexed_db=True),
    }
    values.update(overrides)
    return SessionDescriptor.verified(**values)


def test_auth_state_cannot_transfer_authority():
    desc = _descriptor()
    assert desc.authority_transfer is False
    assert desc.public_receipt()["authority_transfer"] is False
    with pytest.raises(ValueError, match="cannot transfer authority"):
        SessionDescriptor(
            session_ref=desc.session_ref,
            origin=desc.origin,
            identity_context_fingerprint=desc.identity_context_fingerprint,
            created_at=desc.created_at,
            verified_at=desc.verified_at,
            expires_at=desc.expires_at,
            consent=True,
            lifecycle=desc.lifecycle,
            backend_kind=desc.backend_kind,
            backend_healthy=True,
            capabilities=desc.capabilities,
            verification_result="VERIFIED",
            authority_transfer=True,
        )


def test_no_secret_entry_parameters_exist_in_02c_a_core():
    secret_names = {
        "password",
        "passwd",
        "secret",
        "token",
        "access_token",
        "refresh_token",
        "mfa",
        "mfa_code",
        "otp",
        "recovery_code",
        "passkey",
        "private_key",
        "cookie",
        "cookies",
    }
    for callable_object in (SessionValidator.__init__, SessionValidator.validate_for_restore, SessionValidator.open_validated):
        parameters = set(inspect.signature(callable_object).parameters)
        assert secret_names.isdisjoint(parameters)


def test_indexeddb_is_explicit_in_auth_capability_manifest():
    manifest = AuthCapabilityManifest(cookies=True, indexed_db=True)
    assert "indexed_db" in manifest.names()
    assert manifest.to_public_dict()["indexed_db"] is True
    assert manifest.to_public_dict()["session_storage"] is False
    assert manifest.to_public_dict()["virtual_webauthn"] is False


def test_receipt_projection_contains_no_identity_fingerprint_or_lease_owner():
    desc = _descriptor()
    store = InMemorySyntheticProtectedSessionStore(synthetic_test_mode=True)
    store.put_sealed(desc.session_ref, b"synthetic-sealed-state", desc)
    validator = SessionValidator(
        store=store,
        leases=SessionLeaseRegistry(),
        allow_synthetic_backend=True,
    )
    validated = validator.validate_for_restore(
        desc.session_ref,
        target_url=desc.origin,
        identity_context_fingerprint=desc.identity_context_fingerprint,
        owner_execution_id="exec-sensitive-correlation",
        lease_ttl_seconds=5,
        now=desc.created_at + timedelta(minutes=1),
        now_monotonic=1,
    )
    rendered = repr(validated.public_receipt())
    assert desc.identity_context_fingerprint not in rendered
    assert validated.lease.owner_execution_id not in rendered
    assert desc.session_ref.value not in rendered
