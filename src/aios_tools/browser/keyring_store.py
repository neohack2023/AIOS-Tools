from __future__ import annotations

from datetime import datetime
import base64
import hashlib
import json
from typing import Any

from .secret_store import ProtectedBackendUnavailable, ProtectedStoreHealth
from .session import (
    AuthCapabilityManifest,
    OpaqueSessionRef,
    SessionDescriptor,
    SessionLifecycle,
    SessionValidationError,
)


def _descriptor_to_dict(descriptor: SessionDescriptor) -> dict[str, object]:
    return {
        "session_ref": descriptor.session_ref.value,
        "origin": descriptor.origin,
        "identity_context_fingerprint": descriptor.identity_context_fingerprint,
        "created_at": descriptor.created_at.isoformat(),
        "verified_at": descriptor.verified_at.isoformat(),
        "expires_at": descriptor.expires_at.isoformat(),
        "consent": descriptor.consent,
        "lifecycle": descriptor.lifecycle.value,
        "backend_kind": descriptor.backend_kind,
        "backend_healthy": descriptor.backend_healthy,
        "capabilities": descriptor.capabilities.to_public_dict(),
        "verification_result": descriptor.verification_result,
        "authority_transfer": False,
    }


def _descriptor_from_dict(value: dict[str, Any]) -> SessionDescriptor:
    capabilities = value.get("capabilities")
    if not isinstance(capabilities, dict):
        raise SessionValidationError("AUTH_STATE_CORRUPT", "protected session metadata is corrupt")
    try:
        return SessionDescriptor(
            session_ref=OpaqueSessionRef(str(value["session_ref"])),
            origin=str(value["origin"]),
            identity_context_fingerprint=str(value["identity_context_fingerprint"]),
            created_at=datetime.fromisoformat(str(value["created_at"])),
            verified_at=datetime.fromisoformat(str(value["verified_at"])),
            expires_at=datetime.fromisoformat(str(value["expires_at"])),
            consent=bool(value["consent"]),
            lifecycle=SessionLifecycle(str(value["lifecycle"])),
            backend_kind=str(value["backend_kind"]),
            backend_healthy=bool(value["backend_healthy"]),
            capabilities=AuthCapabilityManifest(
                cookies=bool(capabilities.get("cookies")),
                local_storage=bool(capabilities.get("local_storage")),
                indexed_db=bool(capabilities.get("indexed_db")),
                session_storage=bool(capabilities.get("session_storage")),
                virtual_webauthn=bool(capabilities.get("virtual_webauthn")),
            ),
            verification_result=str(value["verification_result"]),
            authority_transfer=False,
        )
    except (KeyError, TypeError, ValueError) as exc:
        raise SessionValidationError("AUTH_STATE_CORRUPT", "protected session metadata is corrupt") from exc


class KeyringProtectedSessionStore:
    """Production session store using an explicitly admitted OS keyring backend."""

    BACKEND_FAMILY = "os-keyring"

    def __init__(
        self,
        *,
        allowed_backend_prefixes: tuple[str, ...],
        keyring_module: Any | None = None,
        service_name: str = "AIOS-Tools/browser-session",
    ) -> None:
        self._allowed_backend_prefixes = tuple(allowed_backend_prefixes)
        self._service_name = service_name
        self._keyring_module = keyring_module
        self._backend = None
        self._backend_path = "unavailable"
        self._initialize_backend()

    def _initialize_backend(self) -> None:
        module = self._keyring_module
        if module is None:
            try:
                import keyring as module
            except ImportError:
                return
        self._keyring_module = module
        try:
            backend = module.get_keyring()
        except Exception:
            return
        path = f"{backend.__class__.__module__}.{backend.__class__.__name__}"
        priority = getattr(backend, "priority", 0)
        try:
            priority_value = float(priority)
        except (TypeError, ValueError):
            priority_value = 0.0
        if priority_value <= 0:
            return
        self._backend_path = path
        if not any(path.startswith(prefix) for prefix in self._allowed_backend_prefixes):
            return
        self._backend = backend

    @property
    def backend_kind(self) -> str:
        return f"{self.BACKEND_FAMILY}:{self._backend_path}"

    def health(self) -> ProtectedStoreHealth:
        admitted = self._backend is not None
        return ProtectedStoreHealth(
            backend_kind=self.backend_kind,
            available=admitted,
            protected=admitted,
            admitted=admitted,
            synthetic=False,
        )

    def _assert_usable(self) -> None:
        if not self.health().usable or self._keyring_module is None:
            raise ProtectedBackendUnavailable()

    def _read_record(self, session_ref: OpaqueSessionRef) -> dict[str, Any] | None:
        self._assert_usable()
        try:
            raw = self._keyring_module.get_password(self._service_name, session_ref.value)
        except Exception as exc:
            raise ProtectedBackendUnavailable() from exc
        if raw is None:
            return None
        try:
            value = json.loads(raw)
        except json.JSONDecodeError as exc:
            raise SessionValidationError("AUTH_STATE_CORRUPT", "protected browser session record is corrupt") from exc
        if not isinstance(value, dict):
            raise SessionValidationError("AUTH_STATE_CORRUPT", "protected browser session record is corrupt")
        return value

    def _index_username(self, origin: str, identity_context_fingerprint: str) -> str:
        material = f"{origin}\0{identity_context_fingerprint}".encode("utf-8")
        return "index:" + hashlib.sha256(material).hexdigest()

    def resolve_ref(self, *, origin: str, identity_context_fingerprint: str) -> OpaqueSessionRef | None:
        self._assert_usable()
        username = self._index_username(origin, identity_context_fingerprint)
        try:
            raw = self._keyring_module.get_password(self._service_name, username)
        except Exception as exc:
            raise ProtectedBackendUnavailable() from exc
        if raw is None:
            return None
        try:
            return OpaqueSessionRef(raw)
        except ValueError as exc:
            raise SessionValidationError("AUTH_STATE_CORRUPT", "protected session index is corrupt") from exc

    def _write_record(self, session_ref: OpaqueSessionRef, record: dict[str, Any]) -> None:
        self._assert_usable()
        try:
            encoded = json.dumps(record, sort_keys=True, separators=(",", ":"))
            self._keyring_module.set_password(self._service_name, session_ref.value, encoded)
        except Exception as exc:
            raise ProtectedBackendUnavailable() from exc

    def put_sealed(self, session_ref: OpaqueSessionRef, sealed_payload: bytes, descriptor: SessionDescriptor) -> None:
        self._assert_usable()
        if descriptor.session_ref != session_ref:
            raise ValueError("session descriptor/ref mismatch")
        if descriptor.backend_kind != self.backend_kind:
            raise ValueError("session descriptor/backend mismatch")
        if not isinstance(sealed_payload, bytes) or not sealed_payload:
            raise ValueError("sealed session payload must be non-empty bytes")
        if descriptor.lifecycle not in {SessionLifecycle.AVAILABLE, SessionLifecycle.IN_USE}:
            raise ValueError("unusable session state cannot be stored as reusable secret material")
        self._write_record(
            session_ref,
            {
                "descriptor": _descriptor_to_dict(descriptor),
                "payload_b64": base64.b64encode(sealed_payload).decode("ascii"),
            },
        )
        try:
            self._keyring_module.set_password(
                self._service_name,
                self._index_username(descriptor.origin, descriptor.identity_context_fingerprint),
                session_ref.value,
            )
        except Exception as exc:
            try:
                self._keyring_module.delete_password(self._service_name, session_ref.value)
            except Exception:
                pass
            raise ProtectedBackendUnavailable() from exc

    def open_sealed(self, session_ref: OpaqueSessionRef) -> bytes:
        record = self._read_record(session_ref)
        if record is None:
            raise SessionValidationError("AUTH_STATE_UNAVAILABLE", "browser authentication state is unavailable")
        raw = record.get("descriptor")
        if not isinstance(raw, dict):
            raise SessionValidationError("AUTH_STATE_CORRUPT", "protected browser session metadata is corrupt")
        descriptor = _descriptor_from_dict(raw)
        if descriptor.lifecycle not in {SessionLifecycle.AVAILABLE, SessionLifecycle.IN_USE}:
            raise SessionValidationError("AUTH_STATE_UNAVAILABLE", "browser authentication state is unavailable")
        payload = record.get("payload_b64")
        if not isinstance(payload, str) or not payload:
            raise SessionValidationError("AUTH_STATE_UNAVAILABLE", "browser authentication state is unavailable")
        try:
            return base64.b64decode(payload.encode("ascii"), validate=True)
        except Exception as exc:
            raise SessionValidationError("AUTH_STATE_CORRUPT", "protected browser session payload is corrupt") from exc

    def metadata(self, session_ref: OpaqueSessionRef) -> SessionDescriptor | None:
        record = self._read_record(session_ref)
        if record is None:
            return None
        raw = record.get("descriptor")
        if not isinstance(raw, dict):
            raise SessionValidationError("AUTH_STATE_CORRUPT", "protected browser session metadata is corrupt")
        return _descriptor_from_dict(raw)

    def mark_lifecycle(self, session_ref: OpaqueSessionRef, lifecycle: SessionLifecycle) -> bool:
        record = self._read_record(session_ref)
        if record is None:
            return False
        raw = record.get("descriptor")
        if not isinstance(raw, dict):
            raise SessionValidationError("AUTH_STATE_CORRUPT", "protected browser session metadata is corrupt")
        descriptor = _descriptor_from_dict(raw).with_lifecycle(lifecycle)
        record["descriptor"] = _descriptor_to_dict(descriptor)
        if lifecycle in {
            SessionLifecycle.EXPIRED,
            SessionLifecycle.REVOKED,
            SessionLifecycle.INVALID,
            SessionLifecycle.PURGED,
        }:
            record["payload_b64"] = None
        self._write_record(session_ref, record)
        return True

    def delete(self, session_ref: OpaqueSessionRef) -> bool:
        self._assert_usable()
        record = self._read_record(session_ref)
        if record is None:
            return False
        descriptor_raw = record.get("descriptor")
        descriptor = _descriptor_from_dict(descriptor_raw) if isinstance(descriptor_raw, dict) else None
        try:
            self._keyring_module.delete_password(self._service_name, session_ref.value)
            if descriptor is not None:
                index_name = self._index_username(descriptor.origin, descriptor.identity_context_fingerprint)
                current = self._keyring_module.get_password(self._service_name, index_name)
                if current == session_ref.value:
                    self._keyring_module.delete_password(self._service_name, index_name)
        except Exception as exc:
            if type(exc).__name__ == "PasswordDeleteError":
                return False
            raise ProtectedBackendUnavailable() from exc
        return True
