from __future__ import annotations

import asyncio
from hashlib import sha256
import json
from pathlib import Path
import re
import socket
from typing import Any, Callable

from .evidence import BrowserEvidence, minimize_url
from .origin import NormalizedOrigin, OriginValidationError, assert_public_origin


ROOT = Path(__file__).resolve().parents[3]
PROFILE_ROOT = ROOT / "profiles" / "browser"
_PROFILE_ID_RE = re.compile(r"^[A-Z][A-Z0-9_]{2,127}$")
_READ_METHODS = frozenset({"GET", "HEAD"})


class BrowserSiteProfileError(RuntimeError):
    pass


def load_site_profile(profile_id: str) -> dict[str, Any]:
    if not isinstance(profile_id, str) or not _PROFILE_ID_RE.fullmatch(profile_id):
        raise BrowserSiteProfileError("invalid browser site profile id")
    path = PROFILE_ROOT / f"{profile_id}.json"
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise BrowserSiteProfileError("browser site profile is unavailable") from exc
    if not isinstance(value, dict) or value.get("profile_id") != profile_id:
        raise BrowserSiteProfileError("browser site profile identity is invalid")
    if value.get("authority_transfer") is not False:
        raise BrowserSiteProfileError("browser site profile may not transfer authority")
    return value


def _profile_network_budget(profile: dict[str, Any]) -> int:
    value = profile.get("validation_network_requests", 120)
    if not isinstance(value, int) or not (1 <= value <= 240):
        raise BrowserSiteProfileError("site profile validation network budget must be 1..240")
    return value


def _profile_resource_origins(profile: dict[str, Any], target_origin: str) -> tuple[NormalizedOrigin, ...]:
    raw = profile.get("resource_origin_allowlist", [])
    if (
        not isinstance(raw, list)
        or len(raw) > 8
        or not all(isinstance(item, str) for item in raw)
    ):
        raise BrowserSiteProfileError("site profile resource-origin allowlist is invalid")
    normalized: dict[str, NormalizedOrigin] = {}
    for item in raw:
        origin = NormalizedOrigin.parse(item)
        rendered = origin.serialize()
        if rendered != target_origin:
            normalized[rendered] = origin
    return tuple(normalized[key] for key in sorted(normalized))


async def _assert_public(origin: NormalizedOrigin, resolver: Callable[..., list[tuple]]) -> tuple[str, ...]:
    return await asyncio.to_thread(assert_public_origin, origin, resolver)


async def _profile_browser_replay(
    profile: dict[str, Any],
    *,
    resolver: Callable[..., list[tuple]] = socket.getaddrinfo,
) -> dict[str, Any]:
    entrypoint = profile["validation_entrypoint"]
    target = NormalizedOrigin.parse(entrypoint)
    target_origin = target.serialize()
    resource_origins = _profile_resource_origins(profile, target_origin)
    admitted_origins = frozenset({target, *resource_origins})
    request_budget = _profile_network_budget(profile)
    elapsed = profile.get("validation_elapsed_seconds", 60)
    visible_limit = profile.get("validation_visible_text_chars", 4000)
    if not isinstance(elapsed, int) or not (1 <= elapsed <= 120):
        raise BrowserSiteProfileError("site profile elapsed budget must be 1..120 seconds")
    if not isinstance(visible_limit, int) or not (1 <= visible_limit <= 10000):
        raise BrowserSiteProfileError("site profile visible-text budget must be 1..10000")

    try:
        await _assert_public(target, resolver)
        for origin in resource_origins:
            await _assert_public(origin, resolver)
    except OriginValidationError as exc:
        raise BrowserSiteProfileError("site profile contains a non-public origin") from exc

    try:
        from playwright.async_api import Error as PlaywrightError
        from playwright.async_api import TimeoutError as PlaywrightTimeoutError
        from playwright.async_api import async_playwright
    except ImportError as exc:
        raise BrowserSiteProfileError("browser optional dependency is not installed") from exc

    context_id = "profile-replay-" + sha256((profile["profile_id"] + entrypoint).encode("utf-8")).hexdigest()[:24]
    evidence = BrowserEvidence(target_origin, context_id)
    fatal = asyncio.Event()
    requests_used = 0
    pages_used = 0
    browser = None
    context = None
    manager = None

    async def route_guard(route, request) -> None:
        nonlocal requests_used
        method = request.method.upper()
        if method not in _READ_METHODS:
            evidence.block(channel="http", url=request.url, reason="HTTP_METHOD_NOT_ADMITTED")
            if request.resource_type == "document":
                fatal.set()
            await route.abort("blockedbyclient")
            return
        try:
            destination = NormalizedOrigin.parse(request.url)
        except OriginValidationError:
            evidence.block(channel="http", url=request.url, reason="ORIGIN_NOT_ADMITTED")
            if request.resource_type == "document":
                fatal.set()
            await route.abort("blockedbyclient")
            return
        if destination not in admitted_origins:
            evidence.block(channel="http", url=request.url, reason="PROFILE_SUBRESOURCE_ORIGIN_NOT_ADMITTED")
            if request.resource_type == "document":
                fatal.set()
            await route.abort("blockedbyclient")
            return
        if request.resource_type == "document" and destination != target:
            evidence.block(channel="navigation", url=request.url, reason="PROFILE_DOCUMENT_ORIGIN_NOT_ADMITTED")
            fatal.set()
            await route.abort("blockedbyclient")
            return
        requests_used += 1
        if requests_used > request_budget:
            evidence.block(channel="http", url=request.url, reason="PROFILE_NETWORK_BUDGET_EXHAUSTED")
            fatal.set()
            await route.abort("blockedbyclient")
            return
        try:
            await _assert_public(destination, resolver)
        except OriginValidationError:
            evidence.block(channel="http", url=request.url, reason="PUBLIC_NETWORK_POLICY_BLOCK")
            fatal.set()
            await route.abort("blockedbyclient")
            return
        evidence.request(method=method, url=request.url, resource_type=request.resource_type, allowed=target)
        await route.continue_()

    async def websocket_guard(ws) -> None:
        evidence.block(channel="websocket", url=ws.url, reason="WEBSOCKET_DISABLED_IN_PROFILE_REPLAY")
        fatal.set()
        await ws.close(code=1008, reason="profile replay websocket blocked")

    def page_guard(page) -> None:
        nonlocal pages_used
        pages_used += 1
        if pages_used > 1:
            evidence.block(channel="page", url=page.url or "about:blank", reason="PROFILE_PAGE_BUDGET_EXHAUSTED")
            fatal.set()
            asyncio.create_task(page.close())

    try:
        async with asyncio.timeout(elapsed):
            manager = async_playwright()
            playwright = await manager.start()
            browser = await playwright.chromium.launch(headless=True)
            context = await browser.new_context(service_workers="block", accept_downloads=False)
            await context.route("**/*", route_guard)
            await context.route_web_socket("**/*", websocket_guard)
            context.on("page", page_guard)
            page = await context.new_page()
            page.on("console", lambda message: evidence.console_event(message.type, message.text))
            page.on("pageerror", lambda exc: evidence.page_error(str(exc)))
            context.on("response", lambda response: evidence.response(url=response.url, status=response.status))
            response = await page.goto(entrypoint, wait_until="domcontentloaded", timeout=elapsed * 1000)
            await asyncio.sleep(0.75)
            main_status = response.status if response is not None else None
            final_url = page.url
            final_summary = minimize_url(final_url)
            visible_text = (await page.locator("body").inner_text())[:visible_limit]
            semantic_success = bool(
                not fatal.is_set()
                and main_status is not None
                and 200 <= main_status < 400
            )
            return {
                "terminal_status": "SUCCEEDED" if semantic_success else "TARGET_BLOCKED",
                "semantic_success": semantic_success,
                "target_origin": target_origin,
                "final_origin": final_summary["origin"],
                "final_path_digest": final_summary["path_digest"],
                "main_response_status": main_status,
                "visible_text": visible_text,
                "fresh_session": True,
                "service_workers": "block",
                "downloads": "block",
                "websockets": "block",
                "budget_used": {
                    "network_requests": requests_used,
                    "pages": pages_used,
                },
                "evidence": evidence.to_dict(),
                "authority_transfer": False,
            }
    except (TimeoutError, PlaywrightTimeoutError):
        evidence.block(channel="profile", url=entrypoint, reason="PROFILE_REPLAY_TIMEOUT")
        return {
            "terminal_status": "BUDGET_EXHAUSTED",
            "semantic_success": False,
            "target_origin": target_origin,
            "final_origin": None,
            "final_path_digest": None,
            "main_response_status": None,
            "visible_text": "",
            "fresh_session": True,
            "budget_used": {"network_requests": requests_used, "pages": pages_used},
            "evidence": evidence.to_dict(),
            "authority_transfer": False,
        }
    except PlaywrightError as exc:
        return {
            "terminal_status": "TARGET_BLOCKED" if fatal.is_set() else "FAILED",
            "semantic_success": False,
            "target_origin": target_origin,
            "final_origin": None,
            "final_path_digest": None,
            "main_response_status": None,
            "visible_text": "",
            "fresh_session": True,
            "budget_used": {"network_requests": requests_used, "pages": pages_used},
            "evidence": evidence.to_dict(),
            "error_type": type(exc).__name__,
            "authority_transfer": False,
        }
    finally:
        if context is not None:
            try:
                await context.close(reason="AIOS site-profile replay complete")
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


async def replay_site_profile_async(profile_id: str) -> dict[str, Any]:
    profile = load_site_profile(profile_id)
    if profile.get("mode") != "REPLAY" or profile.get("effect_class") != "READ_NETWORK":
        raise BrowserSiteProfileError("site profile is not admitted for read-only replay")
    entrypoint = profile.get("validation_entrypoint")
    if not isinstance(entrypoint, str):
        raise BrowserSiteProfileError("site profile validation entrypoint is missing")
    expected_origin = profile.get("origin")
    if not isinstance(expected_origin, str) or NormalizedOrigin.parse(entrypoint).serialize() != expected_origin:
        raise BrowserSiteProfileError("site profile validation origin is inconsistent")
    expected = minimize_url(entrypoint)
    result = await _profile_browser_replay(profile)
    path_match = result.get("final_path_digest") == expected["path_digest"]
    origin_match = result.get("final_origin") == expected_origin
    success = bool(
        result.get("terminal_status") == "SUCCEEDED"
        and result.get("semantic_success") is True
        and path_match
        and origin_match
    )
    visible = result.get("visible_text")
    marker = profile.get("optional_visible_marker")
    marker_observed = bool(isinstance(marker, str) and isinstance(visible, str) and marker in visible)
    return {
        "profile_id": profile_id,
        "profile_version": profile.get("version"),
        "terminal_status": "SUCCEEDED" if success else "PROFILE_STALE",
        "semantic_success": success,
        "target_origin": expected_origin,
        "entrypoint_fingerprint": "sha256:" + sha256(entrypoint.encode("utf-8")).hexdigest(),
        "final_path_digest_match": path_match,
        "final_origin_match": origin_match,
        "optional_marker_observed": marker_observed,
        "fresh_session": True,
        "underlying_terminal_status": result.get("terminal_status"),
        "authority_transfer": False,
        "evidence": result.get("evidence", {}),
        "budget_used": result.get("budget_used", {}),
    }


def run_site_profile_replay(payload: dict[str, Any]) -> dict[str, Any]:
    if set(payload) != {"profile_id"}:
        raise ValueError("browser.profile.replay accepts only profile_id")
    profile_id = payload.get("profile_id")
    try:
        asyncio.get_running_loop()
    except RuntimeError:
        return asyncio.run(replay_site_profile_async(profile_id))
    raise BrowserSiteProfileError("site profile sync bridge cannot run inside an active event loop")
