from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import datetime, timezone
from enum import StrEnum
import hashlib
import re
import secrets
import time
from typing import Iterable

from .origin import NormalizedOrigin, OriginValidationError


_SESSION_REF_RE = re.compile(r"^bs_[0-9a-f]{64}$")
_IDENTITY_FINGERPRINT_RE = re.compile(r"^sha256:[0-9a-f]{64}$")


class SessionLifecycle(StrEnum):
    AVAILABLE = "AVAILABLE"
    IN_USE = "IN_USE"
    EXPIRED = "EXPIRED"
    REVOKED = "REVOKED"
    INVALID = "INVALID"
    PURGED = "PURGED"


class SessionValidationError(RuntimeError):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code


@dataclass(frozen=True, slots=True)
class OpaqueSessionRef:
    value: str

    def __post_init__(self) -> None:
        if not _SESSION_REF_RE.fullmatch(self.value):
            raise ValueError("browser session ref must be an opaque runtime identifier")

    @classmethod
    def new(cls) -> "OpaqueSessionRef":
        return cls(f"bs_{secrets.token_hex(32)}")

    def fingerprint(self) -> str:
        return hashlib.sha256(self.value.encode("ascii")).hexdigest()


@dataclass(frozen=True, slots=True)
class AuthCapabilityManifest:
    cookies: bool = False
    local_storage: bool = False
    indexed_db: bool = False
    session_storage: bool = False
    virtual_webauthn: bool = False

    def names(self) -> frozenset[str]:
        values = {
            "cookies": self.cookies,
            "local_storage": self.local_storage,
            "indexed_db": self.indexed_db,
            "session_storage": self.session_storage,
            "virtual_webauthn": self.virtual_webauthn,
        }
        return frozenset(name for name, present in values.items() if present)

    def satisfies(self, required: Iterable[str]) -> bool:
        return frozenset(required).issubset(self.names())

    def to_public_dict(self) -> dict[str, bool]:
        return {
            "cookies": self.cookies,
            "local_storage": self.local_storage,
            "indexed_db": self.indexed_db,
            "session_storage": self.session_storage,
            "virtual_webauthn": self.virtual_webauthn,
        }


@dataclass(frozen=True, slots=True)
class SessionDescriptor:
    session_ref: OpaqueSessionRef
    origin: str
    identity_context_fingerprint: str
    created_at: datetime
    verified_at: datetime
    expires_at: datetime
    consent: bool
    lifecycle: SessionLifecycle
    backend_kind: str
    backend_healthy: bool
    capabilities: AuthCapabilityManifest
    verification_result: str
    authority_transfer: bool = False

    def __post_init__(self) -> None:
        normalized = NormalizedOrigin.parse(self.origin).serialize()
        if normalized != self.origin:
            raise ValueError("session origin must be exact normalized origin")
        if not _IDENTITY_FINGERPRINT_RE.fullmatch(self.identity_context_fingerprint):
            raise ValueError("identity context must be a sha256 fingerprint")
        for value in (self.created_at, self.verified_at, self.expires_at):
            if value.tzinfo is None or value.utcoffset() is None:
                raise ValueError("session timestamps must be timezone-aware")
        if not (self.created_at <= self.verified_at < self.expires_at):
            raise ValueError("session timestamps must satisfy created <= verified < expires")
        if not self.backend_kind or any(ch.isspace() for ch in self.backend_kind):
            raise ValueError("backend kind must be a compact nonsecret identifier")
        if self.verification_result not in {"VERIFIED", "UNVERIFIED", "FAILED"}:
            raise ValueError("unknown session verification result")
        if self.authority_transfer:
            raise ValueError("browser authentication state cannot transfer authority")

    @classmethod
    def verified(
        cls,
        *,
        origin: str,
        identity_context_fingerprint: str,
        created_at: datetime,
        verified_at: datetime,
        expires_at: datetime,
        backend_kind: str,
        capabilities: AuthCapabilityManifest,
        consent: bool = True,
        session_ref: OpaqueSessionRef | None = None,
    ) -> "SessionDescriptor":
        normalized = NormalizedOrigin.parse(origin).serialize()
        return cls(
            session_ref=session_ref or OpaqueSessionRef.new(),
            origin=normalized,
            identity_context_fingerprint=identity_context_fingerprint,
            created_at=created_at,
            verified_at=verified_at,
            expires_at=expires_at,
            consent=consent,
            lifecycle=SessionLifecycle.AVAILABLE,
            backend_kind=backend_kind,
            backend_healthy=True,
            capabilities=capabilities,
            verification_result="VERIFIED",
            authority_transfer=False,
        )

    def with_lifecycle(self, lifecycle: SessionLifecycle) -> "SessionDescriptor":
        return replace(self, lifecycle=lifecycle)

    def with_backend_health(self, healthy: bool) -> "SessionDescriptor":
        return replace(self, backend_healthy=healthy)

    def is_expired(self, now: datetime) -> bool:
        if now.tzinfo is None or now.utcoffset() is None:
            raise ValueError("now must be timezone-aware")
        return now >= self.expires_at

    def public_receipt(self) -> dict[str, object]:
        return {
            "session_ref_fingerprint": self.session_ref.fingerprint(),
            "origin": self.origin,
            "created_at": self.created_at.astimezone(timezone.utc).isoformat(),
            "verified_at": self.verified_at.astimezone(timezone.utc).isoformat(),
            "expires_at": self.expires_at.astimezone(timezone.utc).isoformat(),
            "consent": self.consent,
            "lifecycle": self.lifecycle.value,
            "backend_kind": self.backend_kind,
            "backend_healthy": self.backend_healthy,
            "capabilities": self.capabilities.to_public_dict(),
            "verification_result": self.verification_result,
            "authority_transfer": False,
        }


@dataclass(frozen=True, slots=True)
class SessionLease:
    session_ref: OpaqueSessionRef
    owner_execution_id: str
    acquired_monotonic: float
    expires_monotonic: float

    def expired(self, now_monotonic: float) -> bool:
        return now_monotonic >= self.expires_monotonic


class SessionLeaseRegistry:
    """Process-local exclusive lease registry. It stores no browser secrets."""

    def __init__(self) -> None:
        self._leases: dict[str, SessionLease] = {}

    def acquire(
        self,
        session_ref: OpaqueSessionRef,
        *,
        owner_execution_id: str,
        ttl_seconds: float,
        now_monotonic: float | None = None,
    ) -> SessionLease:
        if not owner_execution_id or any(ch.isspace() for ch in owner_execution_id):
            raise ValueError("lease owner must be a compact execution identifier")
        if ttl_seconds <= 0:
            raise ValueError("lease ttl must be positive")
        now_value = time.monotonic() if now_monotonic is None else now_monotonic
        current = self._leases.get(session_ref.value)
        if current is not None and not current.expired(now_value):
            raise SessionValidationError("SESSION_LEASE_CONFLICT", "browser session is already leased")
        lease = SessionLease(
            session_ref=session_ref,
            owner_execution_id=owner_execution_id,
            acquired_monotonic=now_value,
            expires_monotonic=now_value + ttl_seconds,
        )
        self._leases[session_ref.value] = lease
        return lease

    def release(self, lease: SessionLease) -> bool:
        current = self._leases.get(lease.session_ref.value)
        if current != lease:
            return False
        del self._leases[lease.session_ref.value]
        return True

    def recover_stale(self, *, now_monotonic: float | None = None) -> int:
        now_value = time.monotonic() if now_monotonic is None else now_monotonic
        stale = [ref for ref, lease in self._leases.items() if lease.expired(now_value)]
        for ref in stale:
            del self._leases[ref]
        return len(stale)


def identity_fingerprint(subject: str) -> str:
    """Create a one-way identity-context fingerprint without retaining the subject."""
    if not isinstance(subject, str) or not subject:
        raise ValueError("identity subject must be non-empty")
    return f"sha256:{hashlib.sha256(subject.encode('utf-8')).hexdigest()}"


def normalized_session_origin(raw: str) -> str:
    try:
        return NormalizedOrigin.parse(raw).serialize()
    except OriginValidationError as exc:
        raise SessionValidationError("SESSION_ORIGIN_INVALID", "session origin is invalid") from exc
