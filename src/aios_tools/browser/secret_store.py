from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from .session import OpaqueSessionRef, SessionDescriptor, SessionLifecycle, SessionValidationError


class ProtectedBackendUnavailable(SessionValidationError):
    def __init__(self) -> None:
        super().__init__("PROTECTED_BACKEND_UNAVAILABLE", "protected browser session backend is unavailable")


@dataclass(frozen=True, slots=True)
class ProtectedStoreHealth:
    backend_kind: str
    available: bool
    protected: bool
    admitted: bool
    synthetic: bool

    @property
    def usable(self) -> bool:
        return self.available and self.protected and self.admitted


class ProtectedSessionStore(Protocol):
    def health(self) -> ProtectedStoreHealth: ...

    def put_sealed(
        self,
        session_ref: OpaqueSessionRef,
        sealed_payload: bytes,
        descriptor: SessionDescriptor,
    ) -> None: ...

    def open_sealed(self, session_ref: OpaqueSessionRef) -> bytes: ...

    def metadata(self, session_ref: OpaqueSessionRef) -> SessionDescriptor | None: ...

    def mark_lifecycle(self, session_ref: OpaqueSessionRef, lifecycle: SessionLifecycle) -> bool: ...

    def delete(self, session_ref: OpaqueSessionRef) -> bool: ...


@dataclass(slots=True)
class _SyntheticRecord:
    descriptor: SessionDescriptor
    sealed_payload: bytes | None


class UnavailableProtectedSessionStore:
    """Production-safe default until an OS-backed protected store is separately admitted."""

    def health(self) -> ProtectedStoreHealth:
        return ProtectedStoreHealth(
            backend_kind="none",
            available=False,
            protected=False,
            admitted=False,
            synthetic=False,
        )

    def _blocked(self) -> None:
        raise ProtectedBackendUnavailable()

    def put_sealed(self, session_ref: OpaqueSessionRef, sealed_payload: bytes, descriptor: SessionDescriptor) -> None:
        self._blocked()

    def open_sealed(self, session_ref: OpaqueSessionRef) -> bytes:
        self._blocked()
        raise AssertionError("unreachable")

    def metadata(self, session_ref: OpaqueSessionRef) -> SessionDescriptor | None:
        self._blocked()
        return None

    def mark_lifecycle(self, session_ref: OpaqueSessionRef, lifecycle: SessionLifecycle) -> bool:
        self._blocked()
        return False

    def delete(self, session_ref: OpaqueSessionRef) -> bool:
        self._blocked()
        return False


class InMemorySyntheticProtectedSessionStore:
    """Synthetic-only test backend. Never use this class for real authentication state."""

    BACKEND_KIND = "synthetic-memory-test"

    def __init__(self, *, synthetic_test_mode: bool) -> None:
        if synthetic_test_mode is not True:
            raise ValueError("synthetic protected store requires explicit test mode")
        self._records: dict[str, _SyntheticRecord] = {}

    def health(self) -> ProtectedStoreHealth:
        return ProtectedStoreHealth(
            backend_kind=self.BACKEND_KIND,
            available=True,
            protected=True,
            admitted=True,
            synthetic=True,
        )

    def _assert_usable(self) -> None:
        if not self.health().usable:
            raise ProtectedBackendUnavailable()

    def put_sealed(
        self,
        session_ref: OpaqueSessionRef,
        sealed_payload: bytes,
        descriptor: SessionDescriptor,
    ) -> None:
        self._assert_usable()
        if descriptor.session_ref != session_ref:
            raise ValueError("session descriptor/ref mismatch")
        if descriptor.backend_kind != self.BACKEND_KIND:
            raise ValueError("session descriptor/backend mismatch")
        if not isinstance(sealed_payload, bytes) or not sealed_payload:
            raise ValueError("sealed session payload must be non-empty bytes")
        if descriptor.lifecycle not in {SessionLifecycle.AVAILABLE, SessionLifecycle.IN_USE}:
            raise ValueError("unusable session state cannot be stored as reusable secret material")
        self._records[session_ref.value] = _SyntheticRecord(descriptor=descriptor, sealed_payload=bytes(sealed_payload))

    def open_sealed(self, session_ref: OpaqueSessionRef) -> bytes:
        self._assert_usable()
        record = self._records.get(session_ref.value)
        if record is None or record.sealed_payload is None:
            raise SessionValidationError("AUTH_STATE_UNAVAILABLE", "browser authentication state is unavailable")
        if record.descriptor.lifecycle not in {SessionLifecycle.AVAILABLE, SessionLifecycle.IN_USE}:
            raise SessionValidationError("AUTH_STATE_UNAVAILABLE", "browser authentication state is unavailable")
        return bytes(record.sealed_payload)

    def metadata(self, session_ref: OpaqueSessionRef) -> SessionDescriptor | None:
        self._assert_usable()
        record = self._records.get(session_ref.value)
        return None if record is None else record.descriptor

    def mark_lifecycle(self, session_ref: OpaqueSessionRef, lifecycle: SessionLifecycle) -> bool:
        self._assert_usable()
        record = self._records.get(session_ref.value)
        if record is None:
            return False
        record.descriptor = record.descriptor.with_lifecycle(lifecycle)
        if lifecycle in {
            SessionLifecycle.EXPIRED,
            SessionLifecycle.REVOKED,
            SessionLifecycle.INVALID,
            SessionLifecycle.PURGED,
        }:
            record.sealed_payload = None
        return True

    def delete(self, session_ref: OpaqueSessionRef) -> bool:
        self._assert_usable()
        return self._records.pop(session_ref.value, None) is not None


def default_protected_session_store() -> ProtectedSessionStore:
    """Use an admitted OS keyring when production session reuse is enabled."""
    import json
    from pathlib import Path

    policy_path = Path(__file__).resolve().parents[3] / "policies" / "browser-auth-policy.v0.1.json"
    try:
        policy = json.loads(policy_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return UnavailableProtectedSessionStore()
    protected = policy.get("protected_store")
    if (
        policy.get("session_reuse_enabled") is not True
        or not isinstance(protected, dict)
        or "os-keyring" not in protected.get("admitted_production_backends", [])
    ):
        return UnavailableProtectedSessionStore()
    prefixes = protected.get("allowed_backend_prefixes")
    if not isinstance(prefixes, list) or not prefixes or not all(isinstance(item, str) and item for item in prefixes):
        return UnavailableProtectedSessionStore()
    from .keyring_store import KeyringProtectedSessionStore

    return KeyringProtectedSessionStore(allowed_backend_prefixes=tuple(prefixes))
