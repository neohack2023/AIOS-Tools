from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from aios_tools.browser.auth import SessionInvalidator, SessionValidator
from aios_tools.browser.secret_store import (
    InMemorySyntheticProtectedSessionStore,
    ProtectedBackendUnavailable,
    default_protected_session_store,
)
from aios_tools.browser.session import (
    AuthCapabilityManifest,
    OpaqueSessionRef,
    SessionDescriptor,
    SessionLeaseRegistry,
    SessionLifecycle,
    SessionValidationError,
    identity_fingerprint,
)


SYNTHETIC_SECRET = b"SYNTHETIC_COOKIE=fixture-secret-never-output"
IDENTITY_SUBJECT = "synthetic-user@example.invalid"
IDENTITY_FP = identity_fingerprint(IDENTITY_SUBJECT)
ORIGIN = "https://example.invalid"


def descriptor(
    *,
    now: datetime | None = None,
    expires_delta: timedelta = timedelta(hours=1),
    capabilities: AuthCapabilityManifest | None = None,
    consent: bool = True,
) -> SessionDescriptor:
    base = now or datetime(2026, 8, 23, 13, 0, tzinfo=timezone.utc)
    return SessionDescriptor.verified(
        origin=ORIGIN,
        identity_context_fingerprint=IDENTITY_FP,
        created_at=base,
        verified_at=base,
        expires_at=base + expires_delta,
        backend_kind=InMemorySyntheticProtectedSessionStore.BACKEND_KIND,
        capabilities=capabilities or AuthCapabilityManifest(cookies=True, local_storage=True),
        consent=consent,
    )


def populated_store(desc: SessionDescriptor | None = None):
    store = InMemorySyntheticProtectedSessionStore(synthetic_test_mode=True)
    current = desc or descriptor()
    store.put_sealed(current.session_ref, SYNTHETIC_SECRET, current)
    return store, current


def validator(store, leases=None, **kwargs):
    return SessionValidator(
        store=store,
        leases=leases or SessionLeaseRegistry(),
        allow_synthetic_backend=True,
        **kwargs,
    )


def test_session_opaque_ref_contains_no_identity_or_origin_material():
    ref = OpaqueSessionRef.new()
    assert ref.value.startswith("bs_")
    assert len(ref.value) == 67
    assert IDENTITY_SUBJECT not in ref.value
    assert "example" not in ref.value
    assert "/" not in ref.value
    assert "\\" not in ref.value


def test_raw_session_ref_is_not_in_public_receipt():
    desc = descriptor()
    receipt = desc.public_receipt()
    rendered = repr(receipt)
    assert desc.session_ref.value not in rendered
    assert SYNTHETIC_SECRET.decode() not in rendered
    assert IDENTITY_SUBJECT not in rendered
    assert receipt["authority_transfer"] is False
    assert len(receipt["session_ref_fingerprint"]) == 64


def test_default_protected_backend_fails_closed_without_plaintext_fallback():
    store = default_protected_session_store()
    assert store.health().usable is False
    with pytest.raises(ProtectedBackendUnavailable) as exc:
        store.metadata(OpaqueSessionRef.new())
    assert exc.value.code == "PROTECTED_BACKEND_UNAVAILABLE"


def test_synthetic_store_requires_explicit_test_mode():
    with pytest.raises(ValueError, match="explicit test mode"):
        InMemorySyntheticProtectedSessionStore(synthetic_test_mode=False)


def test_synthetic_backend_is_rejected_unless_explicitly_admitted():
    store, desc = populated_store()
    runtime_validator = SessionValidator(store=store, leases=SessionLeaseRegistry())
    with pytest.raises(SessionValidationError) as exc:
        runtime_validator.validate_for_restore(
            desc.session_ref,
            target_url=ORIGIN,
            identity_context_fingerprint=IDENTITY_FP,
            owner_execution_id="exec-1",
            lease_ttl_seconds=5,
            now=desc.created_at + timedelta(minutes=1),
            now_monotonic=10,
        )
    assert exc.value.code == "PROTECTED_BACKEND_NOT_ADMITTED"


def test_origin_mismatch_blocks_before_secret_open():
    store, desc = populated_store()
    session_validator = validator(store)
    with pytest.raises(SessionValidationError) as exc:
        session_validator.validate_for_restore(
            desc.session_ref,
            target_url="https://other.invalid",
            identity_context_fingerprint=IDENTITY_FP,
            owner_execution_id="exec-1",
            lease_ttl_seconds=5,
            now=desc.created_at + timedelta(minutes=1),
            now_monotonic=10,
        )
    assert exc.value.code == "SESSION_ORIGIN_MISMATCH"
    assert store.open_sealed(desc.session_ref) == SYNTHETIC_SECRET


def test_identity_mismatch_blocks_before_secret_open():
    store, desc = populated_store()
    session_validator = validator(store)
    with pytest.raises(SessionValidationError) as exc:
        session_validator.validate_for_restore(
            desc.session_ref,
            target_url=ORIGIN,
            identity_context_fingerprint=identity_fingerprint("different@example.invalid"),
            owner_execution_id="exec-1",
            lease_ttl_seconds=5,
            now=desc.created_at + timedelta(minutes=1),
            now_monotonic=10,
        )
    assert exc.value.code == "SESSION_IDENTITY_MISMATCH"


def test_expired_session_is_marked_expired_and_secret_material_is_dropped():
    now = datetime(2026, 8, 23, 13, 0, tzinfo=timezone.utc)
    store, desc = populated_store(descriptor(now=now, expires_delta=timedelta(seconds=1)))
    session_validator = validator(store)
    with pytest.raises(SessionValidationError) as exc:
        session_validator.validate_for_restore(
            desc.session_ref,
            target_url=ORIGIN,
            identity_context_fingerprint=IDENTITY_FP,
            owner_execution_id="exec-1",
            lease_ttl_seconds=5,
            now=now + timedelta(seconds=2),
            now_monotonic=10,
        )
    assert exc.value.code == "SESSION_EXPIRED"
    assert store.metadata(desc.session_ref).lifecycle is SessionLifecycle.EXPIRED
    with pytest.raises(SessionValidationError) as open_exc:
        store.open_sealed(desc.session_ref)
    assert open_exc.value.code == "AUTH_STATE_UNAVAILABLE"


def test_exclusive_lease_blocks_concurrent_session_reuse():
    store, desc = populated_store()
    leases = SessionLeaseRegistry()
    first = validator(store, leases).validate_for_restore(
        desc.session_ref,
        target_url=ORIGIN,
        identity_context_fingerprint=IDENTITY_FP,
        owner_execution_id="exec-1",
        lease_ttl_seconds=30,
        now=desc.created_at + timedelta(minutes=1),
        now_monotonic=10,
    )
    # A second validator cannot treat IN_USE state as AVAILABLE even if it shares the registry.
    with pytest.raises(SessionValidationError) as exc:
        validator(store, leases).validate_for_restore(
            desc.session_ref,
            target_url=ORIGIN,
            identity_context_fingerprint=IDENTITY_FP,
            owner_execution_id="exec-2",
            lease_ttl_seconds=30,
            now=desc.created_at + timedelta(minutes=1),
            now_monotonic=11,
        )
    assert exc.value.code == "AUTH_STATE_UNAVAILABLE"
    assert first.descriptor.lifecycle is SessionLifecycle.IN_USE


def test_release_returns_valid_session_to_available_and_releases_lease():
    store, desc = populated_store()
    leases = SessionLeaseRegistry()
    session_validator = validator(store, leases)
    validated = session_validator.validate_for_restore(
        desc.session_ref,
        target_url=ORIGIN,
        identity_context_fingerprint=IDENTITY_FP,
        owner_execution_id="exec-1",
        lease_ttl_seconds=30,
        now=desc.created_at + timedelta(minutes=1),
        now_monotonic=10,
    )
    assert session_validator.open_validated(validated) == SYNTHETIC_SECRET
    assert session_validator.release(validated, reusable=True) is True
    assert store.metadata(desc.session_ref).lifecycle is SessionLifecycle.AVAILABLE


def test_nonreusable_release_invalidates_and_drops_secret_material():
    store, desc = populated_store()
    session_validator = validator(store)
    validated = session_validator.validate_for_restore(
        desc.session_ref,
        target_url=ORIGIN,
        identity_context_fingerprint=IDENTITY_FP,
        owner_execution_id="exec-1",
        lease_ttl_seconds=30,
        now=desc.created_at + timedelta(minutes=1),
        now_monotonic=10,
    )
    assert session_validator.release(validated, reusable=False) is True
    assert store.metadata(desc.session_ref).lifecycle is SessionLifecycle.INVALID
    with pytest.raises(SessionValidationError):
        store.open_sealed(desc.session_ref)


def test_sessionstorage_requires_separately_reviewed_adapter():
    store, desc = populated_store()
    session_validator = validator(store)
    with pytest.raises(SessionValidationError) as exc:
        session_validator.validate_for_restore(
            desc.session_ref,
            target_url=ORIGIN,
            identity_context_fingerprint=IDENTITY_FP,
            owner_execution_id="exec-1",
            lease_ttl_seconds=5,
            required_capabilities={"session_storage"},
            now=desc.created_at + timedelta(minutes=1),
            now_monotonic=10,
        )
    assert exc.value.code == "SESSION_STORAGE_ADAPTER_REQUIRED"


def test_real_user_virtual_webauthn_persistence_is_blocked_by_default():
    caps = AuthCapabilityManifest(cookies=True, virtual_webauthn=True)
    store, desc = populated_store(descriptor(capabilities=caps))
    session_validator = validator(store)
    with pytest.raises(SessionValidationError) as exc:
        session_validator.validate_for_restore(
            desc.session_ref,
            target_url=ORIGIN,
            identity_context_fingerprint=IDENTITY_FP,
            owner_execution_id="exec-1",
            lease_ttl_seconds=5,
            now=desc.created_at + timedelta(minutes=1),
            now_monotonic=10,
        )
    assert exc.value.code == "VIRTUAL_WEBAUTHN_NOT_ADMITTED"


def test_logout_revokes_local_reusable_state_and_drops_secret():
    store, desc = populated_store()
    invalidator = SessionInvalidator(store)
    assert invalidator.logout(desc.session_ref) is True
    assert store.metadata(desc.session_ref).lifecycle is SessionLifecycle.REVOKED
    with pytest.raises(SessionValidationError):
        store.open_sealed(desc.session_ref)


def test_purge_is_idempotent_at_call_boundary():
    store, desc = populated_store()
    invalidator = SessionInvalidator(store)
    assert invalidator.purge(desc.session_ref) is True
    assert invalidator.purge(desc.session_ref) is False
    assert store.metadata(desc.session_ref) is None


def test_lease_registry_recovers_only_stale_lease():
    leases = SessionLeaseRegistry()
    ref = OpaqueSessionRef.new()
    lease = leases.acquire(ref, owner_execution_id="exec-1", ttl_seconds=5, now_monotonic=10)
    assert leases.recover_stale(now_monotonic=14) == 0
    assert leases.release(lease) is True
    second = leases.acquire(ref, owner_execution_id="exec-2", ttl_seconds=5, now_monotonic=20)
    assert leases.recover_stale(now_monotonic=26) == 1
    assert leases.release(second) is False
