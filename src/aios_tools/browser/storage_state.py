from __future__ import annotations

from dataclasses import replace
import json
from typing import Any, Mapping
from urllib.parse import urlsplit

from .auth import SessionValidator, ValidatedSession
from .origin import NormalizedOrigin, OriginValidationError
from .secret_store import ProtectedSessionStore
from .session import AuthCapabilityManifest, SessionDescriptor, SessionValidationError


_ALLOWED_TOP_LEVEL = frozenset({"cookies", "origins", "credentials"})
_ALLOWED_ORIGIN_FIELDS = frozenset({"origin", "localStorage", "indexedDB"})


def classify_storage_state(state: Mapping[str, Any]) -> AuthCapabilityManifest:
    if not isinstance(state, Mapping):
        raise SessionValidationError("AUTH_STORAGE_STATE_INVALID", "browser storage state must be a mapping")
    unknown_top = set(state) - _ALLOWED_TOP_LEVEL
    if unknown_top:
        raise SessionValidationError("AUTH_STORAGE_STATE_UNKNOWN_FIELD", "browser storage state contains an unknown field")

    cookies = state.get("cookies", [])
    origins = state.get("origins", [])
    credentials = state.get("credentials", [])
    if not isinstance(cookies, list) or not isinstance(origins, list) or not isinstance(credentials, list):
        raise SessionValidationError("AUTH_STORAGE_STATE_INVALID", "browser storage state has an invalid collection")

    has_local = False
    has_indexed = False
    has_session = False
    for origin_state in origins:
        if not isinstance(origin_state, Mapping):
            raise SessionValidationError("AUTH_STORAGE_STATE_INVALID", "browser origin storage state must be a mapping")
        unknown_origin = set(origin_state) - _ALLOWED_ORIGIN_FIELDS
        if unknown_origin:
            if "sessionStorage" in unknown_origin:
                has_session = True
            else:
                raise SessionValidationError("AUTH_STORAGE_STATE_UNKNOWN_FIELD", "browser origin storage state contains an unknown field")
        local = origin_state.get("localStorage", [])
        indexed = origin_state.get("indexedDB", [])
        if not isinstance(local, list) or not isinstance(indexed, list):
            raise SessionValidationError("AUTH_STORAGE_STATE_INVALID", "browser origin storage entries must be lists")
        has_local = has_local or bool(local)
        has_indexed = has_indexed or bool(indexed)

    return AuthCapabilityManifest(
        cookies=bool(cookies),
        local_storage=has_local,
        indexed_db=has_indexed,
        session_storage=has_session,
        virtual_webauthn=bool(credentials),
    )


def _cookie_domain_matches_exact_origin(cookie_domain: str, target_host: str) -> bool:
    normalized = cookie_domain.lstrip(".").lower()
    return normalized == target_host.lower()


def validate_storage_state_scope(state: Mapping[str, Any], descriptor: SessionDescriptor) -> AuthCapabilityManifest:
    manifest = classify_storage_state(state)
    if manifest.session_storage:
        raise SessionValidationError(
            "SESSION_STORAGE_ADAPTER_REQUIRED",
            "sessionStorage authentication requires a separately reviewed adapter",
        )
    if manifest.virtual_webauthn:
        raise SessionValidationError(
            "VIRTUAL_WEBAUTHN_NOT_ADMITTED",
            "virtual WebAuthn credentials are not admitted in the real-user storage-state path",
        )

    try:
        target = NormalizedOrigin.parse(descriptor.origin)
    except OriginValidationError as exc:
        raise SessionValidationError("SESSION_ORIGIN_INVALID", "session descriptor origin is invalid") from exc
    target_host = urlsplit(target.serialize()).hostname
    if target_host is None:
        raise SessionValidationError("SESSION_ORIGIN_INVALID", "session descriptor host is invalid")

    for origin_state in state.get("origins", []):
        raw_origin = origin_state.get("origin")
        if not isinstance(raw_origin, str):
            raise SessionValidationError("AUTH_STORAGE_STATE_INVALID", "storage origin is missing")
        try:
            storage_origin = NormalizedOrigin.parse(raw_origin).serialize()
        except OriginValidationError as exc:
            raise SessionValidationError("AUTH_STORAGE_ORIGIN_INVALID", "storage state contains an invalid origin") from exc
        if storage_origin != descriptor.origin:
            raise SessionValidationError(
                "AUTH_STORAGE_ORIGIN_MISMATCH",
                "storage state contains an origin outside the bound browser session origin",
            )

    for cookie in state.get("cookies", []):
        if not isinstance(cookie, Mapping):
            raise SessionValidationError("AUTH_STORAGE_STATE_INVALID", "storage state cookie must be a mapping")
        domain = cookie.get("domain")
        if not isinstance(domain, str) or not _cookie_domain_matches_exact_origin(domain, target_host):
            raise SessionValidationError(
                "AUTH_STORAGE_COOKIE_SCOPE_MISMATCH",
                "storage state contains a cookie outside the exact browser session host",
            )

    return manifest


def canonical_storage_state_bytes(state: Mapping[str, Any]) -> bytes:
    try:
        return json.dumps(state, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    except (TypeError, ValueError) as exc:
        raise SessionValidationError("AUTH_STORAGE_STATE_INVALID", "browser storage state is not serializable") from exc


def decode_storage_state(payload: bytes) -> dict[str, Any]:
    if not isinstance(payload, bytes) or not payload:
        raise SessionValidationError("AUTH_STATE_UNAVAILABLE", "sealed browser authentication state is unavailable")
    try:
        state = json.loads(payload.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise SessionValidationError("AUTH_STORAGE_STATE_CORRUPT", "protected browser authentication state is corrupt") from exc
    if not isinstance(state, dict):
        raise SessionValidationError("AUTH_STORAGE_STATE_INVALID", "protected browser authentication state is invalid")
    return state


class StorageStateSealer:
    """Keep Playwright storage state in memory and behind ProtectedSessionStore only.

    This class never accepts a filesystem path. The current production policy keeps
    real capture/reuse disabled; the synthetic store is used only for deterministic CI.
    """

    def __init__(self, store: ProtectedSessionStore) -> None:
        self._store = store

    async def capture_context(
        self,
        context: Any,
        descriptor: SessionDescriptor,
    ) -> SessionDescriptor:
        health = self._store.health()
        if not health.usable:
            raise SessionValidationError("PROTECTED_BACKEND_UNAVAILABLE", "protected browser session backend is unavailable")
        state = await context.storage_state(indexed_db=True, credentials=False)
        manifest = validate_storage_state_scope(state, descriptor)
        if manifest.virtual_webauthn:
            raise SessionValidationError("VIRTUAL_WEBAUTHN_NOT_ADMITTED", "virtual WebAuthn state is not admitted")
        updated = replace(descriptor, capabilities=manifest, backend_healthy=True)
        payload = canonical_storage_state_bytes(state)
        self._store.put_sealed(updated.session_ref, payload, updated)
        del state
        del payload
        return updated

    def open_validated_state(
        self,
        validated: ValidatedSession,
        validator: SessionValidator,
    ) -> dict[str, Any]:
        payload = validator.open_validated(validated)
        state = decode_storage_state(payload)
        validate_storage_state_scope(state, validated.descriptor)
        return state

    async def restore_new_context(
        self,
        browser: Any,
        validated: ValidatedSession,
        validator: SessionValidator,
    ) -> Any:
        state = self.open_validated_state(validated, validator)
        try:
            return await browser.new_context(
                storage_state=state,
                service_workers="block",
                accept_downloads=False,
            )
        finally:
            state.clear()
