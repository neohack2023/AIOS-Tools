from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import hmac
from typing import Iterable

from .origin import NormalizedOrigin, OriginValidationError
from .secret_store import ProtectedBackendUnavailable, ProtectedSessionStore
from .session import (
    OpaqueSessionRef,
    SessionDescriptor,
    SessionLease,
    SessionLeaseRegistry,
    SessionLifecycle,
    SessionValidationError,
)


@dataclass(frozen=True, slots=True)
class ValidatedSession:
    descriptor: SessionDescriptor
    lease: SessionLease

    def public_receipt(self) -> dict[str, object]:
        receipt = self.descriptor.public_receipt()
        receipt["lease_owner"] = self.lease.owner_execution_id
        receipt["authority_transfer"] = False
        return receipt


class SessionValidator:
    def __init__(
        self,
        *,
        store: ProtectedSessionStore,
        leases: SessionLeaseRegistry,
        allow_synthetic_backend: bool = False,
        allow_virtual_webauthn_test: bool = False,
    ) -> None:
        self._store = store
        self._leases = leases
        self._allow_synthetic_backend = allow_synthetic_backend
        self._allow_virtual_webauthn_test = allow_virtual_webauthn_test

    def _health(self):
        health = self._store.health()
        if not health.usable:
            raise ProtectedBackendUnavailable()
        if health.synthetic and not self._allow_synthetic_backend:
            raise SessionValidationError(
                "PROTECTED_BACKEND_NOT_ADMITTED",
                "synthetic browser session backend is not admitted for this runtime",
            )
        return health

    def validate_for_restore(
        self,
        session_ref: OpaqueSessionRef,
        *,
        target_url: str,
        identity_context_fingerprint: str,
        owner_execution_id: str,
        lease_ttl_seconds: float,
        required_capabilities: Iterable[str] = (),
        now: datetime | None = None,
        now_monotonic: float | None = None,
    ) -> ValidatedSession:
        health = self._health()
        descriptor = self._store.metadata(session_ref)
        if descriptor is None:
            raise SessionValidationError("AUTH_STATE_UNAVAILABLE", "browser authentication state is unavailable")
        if descriptor.backend_kind != health.backend_kind or not descriptor.backend_healthy:
            raise SessionValidationError("PROTECTED_BACKEND_MISMATCH", "browser session backend identity is not valid")

        try:
            target_origin = NormalizedOrigin.parse(target_url).serialize()
        except OriginValidationError as exc:
            raise SessionValidationError("SESSION_ORIGIN_INVALID", "browser session target origin is invalid") from exc
        if target_origin != descriptor.origin:
            raise SessionValidationError("SESSION_ORIGIN_MISMATCH", "browser session origin does not match the requested target")

        if not hmac.compare_digest(identity_context_fingerprint, descriptor.identity_context_fingerprint):
            raise SessionValidationError(
                "SESSION_IDENTITY_MISMATCH",
                "browser session identity context does not match the requested identity",
            )
        if not descriptor.consent:
            raise SessionValidationError("SESSION_CONSENT_REQUIRED", "browser session consent is not available")
        if descriptor.verification_result != "VERIFIED":
            raise SessionValidationError("AUTH_REQUIRED", "browser authentication state requires verification")
        if descriptor.lifecycle is not SessionLifecycle.AVAILABLE:
            code = "SESSION_EXPIRED" if descriptor.lifecycle is SessionLifecycle.EXPIRED else "AUTH_STATE_UNAVAILABLE"
            raise SessionValidationError(code, "browser authentication state is not reusable")

        now_value = now or datetime.now(timezone.utc)
        if descriptor.is_expired(now_value):
            self._store.mark_lifecycle(session_ref, SessionLifecycle.EXPIRED)
            raise SessionValidationError("SESSION_EXPIRED", "browser authentication state has expired")

        required = frozenset(required_capabilities)
        known = {"cookies", "local_storage", "indexed_db", "session_storage", "virtual_webauthn"}
        unknown = required - known
        if unknown:
            raise SessionValidationError("AUTH_CAPABILITY_UNKNOWN", "unknown browser authentication capability requested")
        if "session_storage" in required:
            raise SessionValidationError(
                "SESSION_STORAGE_ADAPTER_REQUIRED",
                "sessionStorage authentication requires a separately reviewed adapter",
            )
        if "virtual_webauthn" in required and not self._allow_virtual_webauthn_test:
            raise SessionValidationError(
                "VIRTUAL_WEBAUTHN_NOT_ADMITTED",
                "virtual WebAuthn persistence is not admitted for real-user browser sessions",
            )
        if descriptor.capabilities.virtual_webauthn and not self._allow_virtual_webauthn_test:
            raise SessionValidationError(
                "VIRTUAL_WEBAUTHN_NOT_ADMITTED",
                "virtual WebAuthn persistence is not admitted for real-user browser sessions",
            )
        if not descriptor.capabilities.satisfies(required):
            raise SessionValidationError("AUTH_CAPABILITY_MISSING", "browser authentication state lacks a required capability")

        lease = self._leases.acquire(
            session_ref,
            owner_execution_id=owner_execution_id,
            ttl_seconds=lease_ttl_seconds,
            now_monotonic=now_monotonic,
        )
        if not self._store.mark_lifecycle(session_ref, SessionLifecycle.IN_USE):
            self._leases.release(lease)
            raise SessionValidationError("AUTH_STATE_UNAVAILABLE", "browser authentication state disappeared during acquisition")
        in_use = self._store.metadata(session_ref)
        if in_use is None:
            self._leases.release(lease)
            raise SessionValidationError("AUTH_STATE_UNAVAILABLE", "browser authentication state disappeared during acquisition")
        return ValidatedSession(descriptor=in_use, lease=lease)

    def open_validated(self, validated: ValidatedSession) -> bytes:
        current = self._store.metadata(validated.descriptor.session_ref)
        if current is None or current.lifecycle is not SessionLifecycle.IN_USE:
            raise SessionValidationError("AUTH_STATE_UNAVAILABLE", "browser authentication state is not currently leased")
        return self._store.open_sealed(validated.descriptor.session_ref)

    def release(self, validated: ValidatedSession, *, reusable: bool = True) -> bool:
        ref = validated.descriptor.session_ref
        current = self._store.metadata(ref)
        released = self._leases.release(validated.lease)
        if current is None:
            return released
        if reusable and current.lifecycle is SessionLifecycle.IN_USE:
            self._store.mark_lifecycle(ref, SessionLifecycle.AVAILABLE)
        elif not reusable and current.lifecycle is SessionLifecycle.IN_USE:
            self._store.mark_lifecycle(ref, SessionLifecycle.INVALID)
        return released


class SessionInvalidator:
    def __init__(self, store: ProtectedSessionStore) -> None:
        self._store = store

    def revoke(self, session_ref: OpaqueSessionRef) -> bool:
        return self._store.mark_lifecycle(session_ref, SessionLifecycle.REVOKED)

    def expire(self, session_ref: OpaqueSessionRef) -> bool:
        return self._store.mark_lifecycle(session_ref, SessionLifecycle.EXPIRED)

    def invalidate(self, session_ref: OpaqueSessionRef) -> bool:
        return self._store.mark_lifecycle(session_ref, SessionLifecycle.INVALID)

    def logout(self, session_ref: OpaqueSessionRef) -> bool:
        return self.revoke(session_ref)

    def purge(self, session_ref: OpaqueSessionRef) -> bool:
        self._store.mark_lifecycle(session_ref, SessionLifecycle.PURGED)
        return self._store.delete(session_ref)
