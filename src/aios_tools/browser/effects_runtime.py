from __future__ import annotations

import asyncio
from dataclasses import asdict
from datetime import datetime, timezone
import json
import socket
from typing import Any, Callable
from urllib.parse import urlsplit

from .auth import SessionValidator, ValidatedSession
from .mutation import (
    MutationGrant,
    MutationLedger,
    MutationPolicyError,
    canonical_http_url,
)
from .origin import NormalizedOrigin, OriginValidationError, assert_public_origin
from .secret_store import default_protected_session_store
from .session import OpaqueSessionRef, SessionLeaseRegistry
from .storage_state import StorageStateSealer
from .uploads import UploadIntake, UploadLimits, default_artifact_resolver


_SESSION_LEASES = SessionLeaseRegistry()
_MUTATING_METHODS = frozenset({"POST", "PUT", "PATCH", "DELETE"})
_SENSITIVE_HEADERS = frozenset({
    "authorization", "cookie", "proxy-authorization", "set-cookie", "host", "content-length"
})


class BrowserEffectRuntimeUnavailable(RuntimeError):
    pass


class BrowserEffectExecutionError(RuntimeError):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code


def _origin(raw: str) -> str:
    try:
        return NormalizedOrigin.parse(raw).serialize()
    except OriginValidationError as exc:
        raise BrowserEffectExecutionError("TARGET_BLOCKED", "browser effect target origin is invalid") from exc


async def _assert_target(raw: str, *, allow_private_fixture: bool, resolver: Callable[..., list[tuple]]) -> str:
    normalized = _origin(raw)
    if not allow_private_fixture:
        await asyncio.to_thread(assert_public_origin, NormalizedOrigin.parse(raw), resolver)
    return normalized


def _same_origin(first: str, second: str) -> bool:
    return _origin(first) == _origin(second)


def _validate_headers(value: Any) -> dict[str, str]:
    if value is None:
        return {}
    if not isinstance(value, dict) or len(value) > 32:
        raise ValueError("mutation headers must be a small object")
    result: dict[str, str] = {}
    for key, raw in value.items():
        if not isinstance(key, str) or not isinstance(raw, str):
            raise ValueError("mutation headers must contain strings")
        if key.lower() in _SENSITIVE_HEADERS:
            raise ValueError("sensitive or transport-owned mutation header is not admitted")
        if len(key) > 128 or len(raw) > 4096:
            raise ValueError("mutation header exceeds budget")
        result[key] = raw
    return result


def _validate_json_body(value: Any) -> Any:
    if value is None:
        return None
    try:
        encoded = json.dumps(value, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    except (TypeError, ValueError) as exc:
        raise ValueError("mutation json body must be JSON serializable") from exc
    if len(encoded) > 65536:
        raise ValueError("mutation json body exceeds 64 KiB budget")
    return value


def _check_subset(actual: Any, expected: Any) -> bool:
    if isinstance(expected, dict):
        return isinstance(actual, dict) and all(
            key in actual and _check_subset(actual[key], value)
            for key, value in expected.items()
        )
    if isinstance(expected, list):
        return actual == expected
    return actual == expected


async def _readcheck(request_context: Any, check: dict[str, Any], *, target_origin: str, timeout_ms: int) -> dict[str, object]:
    if not isinstance(check, dict):
        raise ValueError("mutation requires a precheck/postcheck object")
    raw_url = check.get("url")
    expected_status = check.get("expected_status")
    if not isinstance(raw_url, str) or not _same_origin(raw_url, target_origin):
        raise ValueError("mutation check URL must stay on exact target origin")
    if not isinstance(expected_status, int) or not (100 <= expected_status <= 599):
        raise ValueError("mutation check expected_status is invalid")
    response = await request_context.get(
        canonical_http_url(raw_url),
        fail_on_status_code=False,
        max_redirects=0,
        max_retries=0,
        timeout=timeout_ms,
    )
    result: dict[str, object] = {"url_fingerprint": __import__("hashlib").sha256(canonical_http_url(raw_url).encode()).hexdigest(), "status": response.status}
    if response.status != expected_status:
        raise BrowserEffectExecutionError("MUTATION_PREPOST_STATE_MISMATCH", "mutation state assertion failed")
    expected_json = check.get("expected_json_subset")
    if expected_json is not None:
        try:
            actual = await response.json()
        except Exception as exc:
            raise BrowserEffectExecutionError("MUTATION_PREPOST_STATE_MISMATCH", "mutation state readback is not JSON") from exc
        if not _check_subset(actual, expected_json):
            raise BrowserEffectExecutionError("MUTATION_PREPOST_STATE_MISMATCH", "mutation JSON state assertion failed")
        result["json_subset_verified"] = True
    return result


async def _new_context(
    browser: Any,
    session: Any,
    *,
    target_url: str,
    owner_execution_id: str,
) -> tuple[Any, SessionValidator | None, ValidatedSession | None]:
    if session is None:
        return (
            await browser.new_context(service_workers="block", accept_downloads=False),
            None,
            None,
        )
    if not isinstance(session, dict):
        raise ValueError("session must be an object")
    raw_ref = session.get("session_ref")
    identity = session.get("identity_context_fingerprint")
    if not isinstance(raw_ref, str) or not isinstance(identity, str):
        raise ValueError("session requires opaque session_ref and identity fingerprint")
    required = session.get("required_capabilities", [])
    if not isinstance(required, list) or not all(isinstance(item, str) for item in required):
        raise ValueError("session required_capabilities must be a list of strings")
    store = default_protected_session_store()
    validator = SessionValidator(store=store, leases=_SESSION_LEASES)
    validated = validator.validate_for_restore(
        OpaqueSessionRef(raw_ref),
        target_url=target_url,
        identity_context_fingerprint=identity,
        owner_execution_id=owner_execution_id,
        lease_ttl_seconds=120,
        required_capabilities=required,
    )
    sealer = StorageStateSealer(store)
    context = await sealer.restore_new_context(browser, validated, validator)
    return context, validator, validated


def _session_receipt(validated: ValidatedSession | None) -> dict[str, object] | None:
    return None if validated is None else validated.public_receipt()


async def mutate_request_async(
    payload: dict[str, Any],
    *,
    allow_private_fixture: bool = False,
    resolver: Callable[..., list[tuple]] = socket.getaddrinfo,
    ledger: MutationLedger | None = None,
) -> dict[str, Any]:
    grant = payload.get("_aios_mutation_grant")
    if not isinstance(grant, MutationGrant):
        raise MutationPolicyError("APPROVAL_REQUIRED", "trusted mutation grant is unavailable")
    allowed = {
        "url", "method", "idempotency_key", "json", "headers", "precheck", "postcheck",
        "expected_status", "timeout_seconds", "session", "_aios_mutation_grant"
    }
    extra = set(payload) - allowed
    if extra:
        raise ValueError("browser.mutate.request contains unsupported fields")
    url = canonical_http_url(payload.get("url"))
    method = str(payload.get("method", "")).upper()
    if method not in _MUTATING_METHODS:
        raise ValueError("mutation HTTP method is not admitted")
    key = payload.get("idempotency_key")
    if not isinstance(key, str):
        raise ValueError("mutation requires idempotency_key")
    timeout_seconds = payload.get("timeout_seconds", 30)
    if not isinstance(timeout_seconds, int) or not (1 <= timeout_seconds <= 60):
        raise ValueError("mutation timeout must be 1..60 seconds")
    expected_status = payload.get("expected_status")
    if not isinstance(expected_status, int) or not (100 <= expected_status <= 599):
        raise ValueError("mutation expected_status is required")
    headers = _validate_headers(payload.get("headers"))
    body = _validate_json_body(payload.get("json"))
    target_origin = await _assert_target(url, allow_private_fixture=allow_private_fixture, resolver=resolver)
    for check_name in ("precheck", "postcheck"):
        check = payload.get(check_name)
        if not isinstance(check, dict) or not isinstance(check.get("url"), str):
            raise ValueError(f"mutation {check_name} is required")
        await _assert_target(check["url"], allow_private_fixture=allow_private_fixture, resolver=resolver)
        if not _same_origin(check["url"], target_origin):
            raise ValueError(f"mutation {check_name} must use exact target origin")

    grant.consume(target_url=url, method=method, idempotency_key=key)
    mutation_ledger = ledger or MutationLedger.default()
    mutation_ledger.reserve(grant)
    mutation_started = False

    try:
        from playwright.async_api import async_playwright
    except ImportError as exc:
        mutation_ledger.mark(key, "FAILED_NO_EFFECT")
        raise BrowserEffectRuntimeUnavailable("browser optional dependency is not installed") from exc

    manager = None
    browser = None
    context = None
    validator = None
    validated = None
    try:
        manager = async_playwright()
        playwright = await manager.start()
        browser = await playwright.chromium.launch(headless=True)
        context, validator, validated = await _new_context(
            browser,
            payload.get("session"),
            target_url=url,
            owner_execution_id=grant.request_id,
        )
        pre = await _readcheck(context.request, payload["precheck"], target_origin=target_origin, timeout_ms=timeout_seconds * 1000)
        mutation_started = True
        response = await context.request.fetch(
            url,
            method=method,
            data=body,
            headers=headers or None,
            fail_on_status_code=False,
            max_redirects=0,
            max_retries=0,
            timeout=timeout_seconds * 1000,
        )
        if response.status != expected_status:
            mutation_ledger.mark(key, "MUTATION_STATE_UNKNOWN")
            return {
                "terminal_status": "MUTATION_STATE_UNKNOWN",
                "semantic_success": False,
                "target_origin": target_origin,
                "method": method,
                "response_status": response.status,
                "precheck": pre,
                "postcheck": None,
                "grant": grant.public_receipt(),
                "auth_state_used": _session_receipt(validated),
                "authority_transfer": False,
            }
        try:
            post = await _readcheck(context.request, payload["postcheck"], target_origin=target_origin, timeout_ms=timeout_seconds * 1000)
        except Exception:
            mutation_ledger.mark(key, "MUTATION_STATE_UNKNOWN")
            return {
                "terminal_status": "MUTATION_STATE_UNKNOWN",
                "semantic_success": False,
                "target_origin": target_origin,
                "method": method,
                "response_status": response.status,
                "precheck": pre,
                "postcheck": None,
                "grant": grant.public_receipt(),
                "auth_state_used": _session_receipt(validated),
                "authority_transfer": False,
            }
        mutation_ledger.mark(key, "SUCCEEDED")
        return {
            "terminal_status": "SUCCEEDED",
            "semantic_success": True,
            "target_origin": target_origin,
            "method": method,
            "response_status": response.status,
            "precheck": pre,
            "postcheck": post,
            "grant": grant.public_receipt(),
            "auth_state_used": _session_receipt(validated),
            "authority_transfer": False,
        }
    except Exception:
        status = mutation_ledger.status(key)
        if status == "STARTED":
            mutation_ledger.mark(key, "MUTATION_STATE_UNKNOWN" if mutation_started else "FAILED_NO_EFFECT")
        raise
    finally:
        if validator is not None and validated is not None:
            try:
                validator.release(validated, reusable=True)
            except Exception:
                pass
        if context is not None:
            try:
                await context.close(reason="AIOS mutation request complete")
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


def _locator(page: Any, spec: Any) -> Any:
    if not isinstance(spec, dict):
        raise ValueError("upload locator must be an object")
    strategy = spec.get("strategy")
    value = spec.get("value")
    if not isinstance(value, str) or not value or len(value) > 256:
        raise ValueError("upload locator value is invalid")
    if strategy == "label":
        return page.get_by_label(value, exact=True)
    if strategy == "test_id":
        return page.get_by_test_id(value)
    raise ValueError("upload locator strategy must be label or test_id")


async def upload_execute_async(
    payload: dict[str, Any],
    *,
    allow_private_fixture: bool = False,
    resolver: Callable[..., list[tuple]] = socket.getaddrinfo,
    ledger: MutationLedger | None = None,
    artifact_resolver: Any | None = None,
    artifact_root: Any | None = None,
) -> dict[str, Any]:
    grant = payload.get("_aios_mutation_grant")
    if not isinstance(grant, MutationGrant):
        raise MutationPolicyError("APPROVAL_REQUIRED", "trusted mutation grant is unavailable")
    allowed = {
        "page_url", "mutation_url", "method", "idempotency_key", "artifact_ref",
        "file_locator", "submit_locator", "postcheck", "expected_status",
        "timeout_seconds", "session", "_aios_mutation_grant"
    }
    if set(payload) - allowed:
        raise ValueError("browser.upload.execute contains unsupported fields")
    page_url = canonical_http_url(payload.get("page_url"))
    mutation_url = canonical_http_url(payload.get("mutation_url"))
    method = str(payload.get("method", "")).upper()
    key = payload.get("idempotency_key")
    if method not in _MUTATING_METHODS or not isinstance(key, str):
        raise ValueError("upload mutation method/idempotency key is invalid")
    if not _same_origin(page_url, mutation_url):
        raise ValueError("upload page and mutation target must share exact origin")
    target_origin = await _assert_target(mutation_url, allow_private_fixture=allow_private_fixture, resolver=resolver)
    await _assert_target(page_url, allow_private_fixture=allow_private_fixture, resolver=resolver)
    timeout_seconds = payload.get("timeout_seconds", 30)
    if not isinstance(timeout_seconds, int) or not (1 <= timeout_seconds <= 60):
        raise ValueError("upload timeout must be 1..60 seconds")
    expected_status = payload.get("expected_status")
    if not isinstance(expected_status, int):
        raise ValueError("upload expected_status is required")
    postcheck = payload.get("postcheck")
    if not isinstance(postcheck, dict) or not isinstance(postcheck.get("url"), str) or not _same_origin(postcheck["url"], target_origin):
        raise ValueError("upload postcheck must use exact target origin")

    resolver_obj = artifact_resolver or default_artifact_resolver()
    root = artifact_root if artifact_root is not None else getattr(resolver_obj, "artifact_root", None)
    if root is None:
        raise ValueError("governed artifact root is unavailable")
    intake = UploadIntake(resolver_obj, artifact_root=root, limits=UploadLimits(max_file_bytes=52428800))
    prepared = intake.prepare(payload.get("artifact_ref"))

    grant.consume(target_url=mutation_url, method=method, idempotency_key=key)
    mutation_ledger = ledger or MutationLedger.default()
    mutation_ledger.reserve(grant)
    mutation_started = False
    mutation_count = 0
    mutation_response_status: int | None = None
    blocked_event = asyncio.Event()
    mutation_event = asyncio.Event()
    response_event = asyncio.Event()

    try:
        from playwright.async_api import async_playwright
    except ImportError as exc:
        mutation_ledger.mark(key, "FAILED_NO_EFFECT")
        raise BrowserEffectRuntimeUnavailable("browser optional dependency is not installed") from exc

    manager = None
    browser = None
    context = None
    validator = None
    validated = None

    async def route_guard(route: Any, request: Any) -> None:
        nonlocal mutation_count, mutation_started
        try:
            request_url = canonical_http_url(request.url)
        except Exception:
            blocked_event.set()
            await route.abort("blockedbyclient")
            return
        request_method = request.method.upper()
        if not _same_origin(request_url, target_origin):
            blocked_event.set()
            await route.abort("blockedbyclient")
            return
        if request_method in {"GET", "HEAD"}:
            await route.continue_()
            return
        if request_method == method and request_url == mutation_url and mutation_count == 0:
            mutation_count += 1
            mutation_started = True
            mutation_event.set()
            await route.continue_()
            return
        blocked_event.set()
        await route.abort("blockedbyclient")

    try:
        manager = async_playwright()
        playwright = await manager.start()
        browser = await playwright.chromium.launch(headless=True)
        context, validator, validated = await _new_context(
            browser,
            payload.get("session"),
            target_url=page_url,
            owner_execution_id=grant.request_id,
        )
        await context.route("**/*", route_guard)

        page = await context.new_page()

        def on_response(response: Any) -> None:
            nonlocal mutation_response_status
            try:
                if response.request.method.upper() == method and canonical_http_url(response.url) == mutation_url:
                    mutation_response_status = response.status
                    response_event.set()
            except Exception:
                return

        context.on("response", on_response)
        response = await page.goto(page_url, wait_until="load", timeout=timeout_seconds * 1000)
        if response is None or not (200 <= response.status < 400) or blocked_event.is_set():
            mutation_ledger.mark(key, "FAILED_NO_EFFECT")
            return {
                "terminal_status": "MUTATION_BLOCKED",
                "semantic_success": False,
                "target_origin": target_origin,
                "method": method,
                "mutation_count": mutation_count,
                "authority_transfer": False,
            }

        file_locator = _locator(page, payload.get("file_locator"))
        if await file_locator.count() != 1 or not await file_locator.is_visible():
            mutation_ledger.mark(key, "FAILED_NO_EFFECT")
            raise BrowserEffectExecutionError("UPLOAD_BLOCKED", "file input pre-state assertion failed")
        input_type = await file_locator.get_attribute("type")
        if input_type != "file":
            mutation_ledger.mark(key, "FAILED_NO_EFFECT")
            raise BrowserEffectExecutionError("UPLOAD_BLOCKED", "target is not a file input")

        await file_locator.set_input_files(prepared.playwright_file_payload())
        try:
            await asyncio.wait_for(mutation_event.wait(), timeout=0.35)
        except TimeoutError:
            submit_spec = payload.get("submit_locator")
            if submit_spec is None:
                mutation_ledger.mark(key, "FAILED_NO_EFFECT")
                return {
                    "terminal_status": "MUTATION_NOT_OBSERVED",
                    "semantic_success": False,
                    "target_origin": target_origin,
                    "method": method,
                    "mutation_count": 0,
                    "upload_artifact": prepared.receipt.to_dict(),
                    "grant": grant.public_receipt(),
                    "authority_transfer": False,
                }
            submit = _locator(page, submit_spec)
            if await submit.count() != 1 or not await submit.is_visible():
                mutation_ledger.mark(key, "FAILED_NO_EFFECT")
                raise BrowserEffectExecutionError("MUTATION_BLOCKED", "submit pre-state assertion failed")
            await submit.click()

        try:
            await asyncio.wait_for(response_event.wait(), timeout=timeout_seconds)
        except TimeoutError:
            mutation_ledger.mark(key, "MUTATION_STATE_UNKNOWN" if mutation_started else "FAILED_NO_EFFECT")
            return {
                "terminal_status": "MUTATION_STATE_UNKNOWN" if mutation_started else "MUTATION_NOT_OBSERVED",
                "semantic_success": False,
                "target_origin": target_origin,
                "method": method,
                "mutation_count": mutation_count,
                "upload_artifact": prepared.receipt.to_dict(),
                "grant": grant.public_receipt(),
                "authority_transfer": False,
            }
        if blocked_event.is_set() or mutation_count != 1 or mutation_response_status != expected_status:
            mutation_ledger.mark(key, "MUTATION_STATE_UNKNOWN" if mutation_started else "FAILED_NO_EFFECT")
            return {
                "terminal_status": "MUTATION_STATE_UNKNOWN" if mutation_started else "MUTATION_BLOCKED",
                "semantic_success": False,
                "target_origin": target_origin,
                "method": method,
                "response_status": mutation_response_status,
                "mutation_count": mutation_count,
                "upload_artifact": prepared.receipt.to_dict(),
                "grant": grant.public_receipt(),
                "authority_transfer": False,
            }
        try:
            post = await _readcheck(context.request, postcheck, target_origin=target_origin, timeout_ms=timeout_seconds * 1000)
        except Exception:
            mutation_ledger.mark(key, "MUTATION_STATE_UNKNOWN")
            return {
                "terminal_status": "MUTATION_STATE_UNKNOWN",
                "semantic_success": False,
                "target_origin": target_origin,
                "method": method,
                "response_status": mutation_response_status,
                "mutation_count": mutation_count,
                "upload_artifact": prepared.receipt.to_dict(),
                "grant": grant.public_receipt(),
                "authority_transfer": False,
            }
        mutation_ledger.mark(key, "SUCCEEDED")
        return {
            "terminal_status": "SUCCEEDED",
            "semantic_success": True,
            "target_origin": target_origin,
            "method": method,
            "response_status": mutation_response_status,
            "mutation_count": mutation_count,
            "postcheck": post,
            "upload_artifact": prepared.receipt.to_dict(),
            "grant": grant.public_receipt(),
            "auth_state_used": _session_receipt(validated),
            "authority_transfer": False,
        }
    except Exception:
        status = mutation_ledger.status(key)
        if status == "STARTED":
            mutation_ledger.mark(key, "MUTATION_STATE_UNKNOWN" if mutation_started else "FAILED_NO_EFFECT")
        raise
    finally:
        if validator is not None and validated is not None:
            try:
                validator.release(validated, reusable=True)
            except Exception:
                pass
        if context is not None:
            try:
                await context.close(reason="AIOS live upload complete")
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


def run_mutation_request(payload: dict[str, Any]) -> dict[str, Any]:
    try:
        asyncio.get_running_loop()
    except RuntimeError:
        return asyncio.run(mutate_request_async(payload))
    raise BrowserEffectRuntimeUnavailable("browser mutation sync bridge cannot run inside an active event loop")


def run_upload_execute(payload: dict[str, Any]) -> dict[str, Any]:
    try:
        asyncio.get_running_loop()
    except RuntimeError:
        return asyncio.run(upload_execute_async(payload))
    raise BrowserEffectRuntimeUnavailable("browser upload sync bridge cannot run inside an active event loop")
