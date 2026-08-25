from __future__ import annotations

import asyncio
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from hashlib import sha256
import hmac
import json
import re
import socket
from typing import Any, Awaitable, Callable

from .models import SemanticLocator
from .origin import NormalizedOrigin, OriginValidationError, assert_public_origin
from .secret_store import ProtectedSessionStore, default_protected_session_store
from .session import AuthCapabilityManifest, SessionDescriptor
from .storage_state import StorageStateSealer
from .takeover import (
    TakeoverOriginGate,
    TakeoverResumeProof,
    TakeoverState,
    UserTakeoverCheckpoint,
)


_COMPACT_ID_RE = re.compile(r"^[A-Za-z0-9_.:-]{1,128}$")
_IDENTITY_RE = re.compile(r"^sha256:[0-9a-f]{64}$")
_ALLOWED_AUTH_METHODS = frozenset({"GET", "HEAD", "POST"})


class SessionCapturePolicyError(RuntimeError):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code


@dataclass(slots=True)
class SessionCaptureGrant:
    request_id: str
    tool: str
    scope: str
    target_origin: str
    identity_context_fingerprint: str
    transition_origins: tuple[str, ...]
    approval_id: str
    approved_by: str
    capture_key: str
    expires_at: datetime
    _consumed: bool = False

    def consume(self) -> None:
        if self._consumed:
            raise SessionCapturePolicyError("AUTH_CAPTURE_GRANT_CONSUMED", "session capture approval is one-shot")
        if datetime.now(timezone.utc) >= self.expires_at:
            raise SessionCapturePolicyError("APPROVAL_EXPIRED", "session capture approval has expired")
        self._consumed = True

    def public_receipt(self) -> dict[str, object]:
        transitions = json.dumps(self.transition_origins, separators=(",", ":"))
        return {
            "approval_id_fingerprint": "sha256:" + sha256(self.approval_id.encode()).hexdigest(),
            "approved_by_fingerprint": "sha256:" + sha256(self.approved_by.encode()).hexdigest(),
            "target_origin": self.target_origin,
            "identity_context_exposed": False,
            "transition_origins_fingerprint": "sha256:" + sha256(transitions.encode()).hexdigest(),
            "capture_key_fingerprint": "sha256:" + sha256(self.capture_key.encode()).hexdigest(),
            "one_shot": True,
            "authority_transfer": False,
        }


def _normalized_origin(raw: str) -> str:
    try:
        return NormalizedOrigin.parse(raw).serialize()
    except OriginValidationError as exc:
        raise SessionCapturePolicyError("SESSION_ORIGIN_INVALID", "session capture origin is invalid") from exc


def _transition_digest(origins: tuple[str, ...]) -> str:
    encoded = json.dumps(origins, separators=(",", ":")).encode()
    return "sha256:" + sha256(encoded).hexdigest()


def build_session_capture_grant(
    *,
    request_id: str,
    tool: str,
    scope: str,
    effect_class: str,
    payload: dict[str, Any],
    authority_context: dict[str, Any],
    now: datetime | None = None,
) -> SessionCaptureGrant:
    if effect_class != "REMOTE_MUTATION_HIGH_IMPACT":
        raise SessionCapturePolicyError("EFFECT_CLASS_BLOCKED", "session capture requires high-impact effect classification")
    url = payload.get("url")
    identity = payload.get("identity_context_fingerprint")
    capture_key = payload.get("capture_key")
    transitions_raw = payload.get("explicit_transition_origins", [])
    if not isinstance(url, str) or not url:
        raise SessionCapturePolicyError("SESSION_ORIGIN_INVALID", "session capture requires url")
    target_origin = _normalized_origin(url)
    if not isinstance(identity, str) or not _IDENTITY_RE.fullmatch(identity):
        raise SessionCapturePolicyError("SESSION_IDENTITY_INVALID", "session capture requires identity-context fingerprint")
    if not isinstance(capture_key, str) or not _COMPACT_ID_RE.fullmatch(capture_key):
        raise SessionCapturePolicyError("AUTH_CAPTURE_KEY_REQUIRED", "session capture requires compact capture_key")
    if (
        not isinstance(transitions_raw, list)
        or len(transitions_raw) > 8
        or not all(isinstance(item, str) for item in transitions_raw)
    ):
        raise SessionCapturePolicyError("TAKEOVER_ORIGIN_BLOCKED", "session capture transition origin list is invalid")
    transitions = tuple(sorted({_normalized_origin(item) for item in transitions_raw if _normalized_origin(item) != target_origin}))

    approval = authority_context.get("approval")
    if not isinstance(approval, dict) or approval.get("approved") is not True:
        raise SessionCapturePolicyError("APPROVAL_REQUIRED", "session capture requires explicit approval")
    exact = {
        "tool": tool,
        "scope": scope,
        "effect_class": effect_class,
        "target_origin": target_origin,
        "identity_context_fingerprint": identity,
        "transition_origins_fingerprint": _transition_digest(transitions),
        "capture_key": capture_key,
    }
    for field, expected in exact.items():
        actual = approval.get(field)
        if not isinstance(actual, str) or not hmac.compare_digest(actual, expected):
            raise SessionCapturePolicyError("APPROVAL_SCOPE_MISMATCH", f"session capture approval {field} does not match")
    if approval.get("one_shot") is not True or approval.get("high_impact_ack") is not True:
        raise SessionCapturePolicyError("APPROVAL_REQUIRED", "session capture approval must be one-shot and acknowledge high impact")
    approval_id = approval.get("approval_id")
    approved_by = approval.get("approved_by")
    if not isinstance(approval_id, str) or not _COMPACT_ID_RE.fullmatch(approval_id):
        raise SessionCapturePolicyError("APPROVAL_INVALID", "session capture approval requires approval_id")
    if not isinstance(approved_by, str) or not approved_by.strip():
        raise SessionCapturePolicyError("APPROVAL_INVALID", "session capture approval requires approved_by")
    expires_raw = approval.get("expires_at")
    if not isinstance(expires_raw, str):
        raise SessionCapturePolicyError("APPROVAL_INVALID", "session capture approval requires expires_at")
    try:
        expires = datetime.fromisoformat(expires_raw.replace("Z", "+00:00"))
    except ValueError as exc:
        raise SessionCapturePolicyError("APPROVAL_INVALID", "session capture approval expiry is invalid") from exc
    if expires.tzinfo is None or expires.utcoffset() is None:
        raise SessionCapturePolicyError("APPROVAL_INVALID", "session capture approval expiry must be timezone-aware")
    now_value = (now or datetime.now(timezone.utc)).astimezone(timezone.utc)
    expires = expires.astimezone(timezone.utc)
    if expires <= now_value:
        raise SessionCapturePolicyError("APPROVAL_EXPIRED", "session capture approval has expired")
    if (expires - now_value).total_seconds() > 900:
        raise SessionCapturePolicyError("APPROVAL_INVALID", "session capture approval may not exceed 15 minutes")
    return SessionCaptureGrant(
        request_id=request_id,
        tool=tool,
        scope=scope,
        target_origin=target_origin,
        identity_context_fingerprint=identity,
        transition_origins=transitions,
        approval_id=approval_id,
        approved_by=approved_by,
        capture_key=capture_key,
        expires_at=expires,
    )


def _locator(page: Any, spec: dict[str, Any]) -> Any:
    locator = SemanticLocator(
        kind=spec.get("kind"),
        value=spec.get("value"),
        accessible_name=spec.get("accessible_name"),
        exact=bool(spec.get("exact", True)),
    )
    if locator.kind == "role":
        if not locator.accessible_name:
            raise ValueError("role verification locator requires accessible_name")
        return page.get_by_role(locator.value, name=locator.accessible_name, exact=locator.exact)
    if locator.kind == "label":
        return page.get_by_label(locator.value, exact=locator.exact)
    if locator.kind == "test_id":
        return page.get_by_test_id(locator.value)
    return page.get_by_text(locator.value, exact=locator.exact)


async def capture_session_async(
    payload: dict[str, Any],
    *,
    store: ProtectedSessionStore | None = None,
    resolver: Callable[..., list[tuple]] = socket.getaddrinfo,
    allow_private_fixture: bool = False,
    headless_fixture: bool = False,
    fixture_user_action: Callable[[Any], Awaitable[None]] | None = None,
) -> dict[str, Any]:
    grant = payload.get("_aios_session_capture_grant")
    if not isinstance(grant, SessionCaptureGrant):
        raise SessionCapturePolicyError("APPROVAL_REQUIRED", "trusted session capture grant is unavailable")
    allowed = {
        "url",
        "identity_context_fingerprint",
        "capture_key",
        "explicit_transition_origins",
        "verification_locator",
        "takeover_timeout_seconds",
        "session_ttl_seconds",
        "_aios_session_capture_grant",
    }
    if set(payload) - allowed:
        raise ValueError("browser.session.capture contains unsupported fields")
    if payload.get("identity_context_fingerprint") != grant.identity_context_fingerprint:
        raise SessionCapturePolicyError("APPROVAL_SCOPE_MISMATCH", "session capture identity changed after approval")
    target_url = payload.get("url")
    if not isinstance(target_url, str) or _normalized_origin(target_url) != grant.target_origin:
        raise SessionCapturePolicyError("APPROVAL_SCOPE_MISMATCH", "session capture target changed after approval")
    verification_locator = payload.get("verification_locator")
    if not isinstance(verification_locator, dict):
        raise ValueError("session capture requires semantic verification_locator")
    timeout_seconds = payload.get("takeover_timeout_seconds", 300)
    ttl_seconds = payload.get("session_ttl_seconds", 28800)
    if not isinstance(timeout_seconds, int) or not (15 <= timeout_seconds <= 900):
        raise ValueError("takeover timeout must be 15..900 seconds")
    if not isinstance(ttl_seconds, int) or not (60 <= ttl_seconds <= 86400):
        raise ValueError("session ttl must be 60..86400 seconds")

    store_obj = store or default_protected_session_store()
    health = store_obj.health()
    if not health.usable:
        raise SessionCapturePolicyError("PROTECTED_BACKEND_UNAVAILABLE", "protected browser session backend is unavailable")
    if health.synthetic and not headless_fixture:
        raise SessionCapturePolicyError("PROTECTED_BACKEND_NOT_ADMITTED", "synthetic session backend is test-only")

    if not allow_private_fixture:
        await asyncio.to_thread(assert_public_origin, NormalizedOrigin.parse(target_url), resolver)
        for origin in grant.transition_origins:
            await asyncio.to_thread(assert_public_origin, NormalizedOrigin.parse(origin), resolver)

    grant.consume()

    try:
        from playwright.async_api import async_playwright
    except ImportError as exc:
        raise RuntimeError("browser optional dependency is not installed") from exc

    manager = None
    browser = None
    context = None
    outcome = None
    created_at = datetime.now(timezone.utc)
    mutation_count = 0
    blocked_event = asyncio.Event()
    checkpoint = UserTakeoverCheckpoint(
        target_origin=grant.target_origin,
        timeout_seconds=timeout_seconds,
        explicit_transition_origins=grant.transition_origins,
    )

    async def route_guard(route: Any, request: Any) -> None:
        nonlocal mutation_count
        try:
            checkpoint.origin_gate.observe(request.url)
        except Exception:
            blocked_event.set()
            await route.abort("blockedbyclient")
            return
        method = request.method.upper()
        if method not in _ALLOWED_AUTH_METHODS:
            blocked_event.set()
            await route.abort("blockedbyclient")
            return
        if method == "POST":
            mutation_count += 1
            if mutation_count > 20:
                blocked_event.set()
                await route.abort("blockedbyclient")
                return
        await route.continue_()

    async def ws_guard(ws: Any) -> None:
        await ws.close(code=1008, reason="AIOS auth takeover blocks WebSocket")

    try:
        manager = async_playwright()
        playwright = await manager.start()
        browser = await playwright.chromium.launch(headless=headless_fixture)
        context = await browser.new_context(service_workers="block", accept_downloads=False)
        await context.route("**/*", route_guard)
        await context.route_web_socket("**/*", ws_guard)
        page = await context.new_page()
        await page.goto(target_url, wait_until="domcontentloaded", timeout=min(timeout_seconds, 60) * 1000)

        async def verified_page() -> Any | None:
            for candidate in list(context.pages):
                if candidate.is_closed() or candidate.url == "about:blank":
                    continue
                try:
                    if checkpoint.origin_gate.observe(candidate.url) != grant.target_origin:
                        continue
                except Exception:
                    continue
                locator = _locator(candidate, verification_locator)
                try:
                    if await locator.count() == 1 and await locator.is_visible():
                        return candidate
                except Exception:
                    continue
            return None

        async def user_control(blackout: Any, gate: TakeoverOriginGate) -> None:
            del blackout, gate
            if fixture_user_action is not None:
                await fixture_user_action(page)
            while True:
                if blocked_event.is_set():
                    raise SessionCapturePolicyError("AUTH_FLOW_BLOCKED", "authentication flow exceeded its admitted boundary")
                if await verified_page() is not None:
                    return
                await asyncio.sleep(0.2)

        async def verifier() -> TakeoverResumeProof | None:
            candidate = await verified_page()
            if candidate is None:
                return None
            return TakeoverResumeProof(
                origin=grant.target_origin,
                identity_context_fingerprint=grant.identity_context_fingerprint,
                verified_at=datetime.now(timezone.utc),
                verification_method="semantic_locator_exact_origin",
                authenticated=True,
            )

        outcome = await checkpoint.run(
            user_control=user_control,
            verifier=verifier,
        )
        if outcome.state is not TakeoverState.SESSION_AVAILABLE or outcome.proof is None:
            return {
                "terminal_status": outcome.state.value,
                "semantic_success": False,
                "target_origin": grant.target_origin,
                "method": "AUTH_FLOW",
                "mutation_count": mutation_count,
                "takeover": outcome.public_receipt(),
                "grant": grant.public_receipt(),
                "authority_transfer": False,
            }

        descriptor = SessionDescriptor.verified(
            origin=grant.target_origin,
            identity_context_fingerprint=grant.identity_context_fingerprint,
            created_at=created_at,
            verified_at=outcome.proof.verified_at,
            expires_at=outcome.proof.verified_at + timedelta(seconds=ttl_seconds),
            backend_kind=health.backend_kind,
            capabilities=AuthCapabilityManifest(),
        )
        descriptor = await StorageStateSealer(store_obj).capture_context(context, descriptor)
        return {
            "terminal_status": "SESSION_AVAILABLE",
            "semantic_success": True,
            "target_origin": grant.target_origin,
            "method": "AUTH_FLOW",
            "mutation_count": mutation_count,
            "session": descriptor.public_receipt(),
            "takeover": outcome.public_receipt(),
            "grant": grant.public_receipt(),
            "raw_session_ref_exposed": False,
            "authority_transfer": False,
        }
    finally:
        if context is not None:
            try:
                await context.close(reason="AIOS authentication takeover complete")
            except Exception:
                pass
        if browser is not None:
            try:
                await browser.close()
            except Exception:
                pass
        if manager is not None:
            try:
                await manager.__aexit__(None, None, None)
            except Exception:
                pass


def run_session_capture(payload: dict[str, Any]) -> dict[str, Any]:
    try:
        asyncio.get_running_loop()
    except RuntimeError:
        return asyncio.run(capture_session_async(payload))
    raise RuntimeError("browser session capture sync bridge cannot run inside an active event loop")
