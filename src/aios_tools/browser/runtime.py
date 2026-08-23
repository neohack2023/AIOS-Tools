from __future__ import annotations

import asyncio
from pathlib import Path
import socket
import tempfile
from typing import Any, Awaitable, Callable
from uuid import uuid4

from .budget import BudgetExceeded, BudgetLedger
from .evidence import BrowserEvidence
from .origin import NormalizedOrigin, OriginValidationError, assert_public_origin, same_http_origin, same_websocket_origin
from .policy import load_browser_policy


class BrowserRuntimeUnavailable(RuntimeError):
    pass


class BrowserExecutionBlocked(RuntimeError):
    pass


class RunPaths:
    def __init__(self, root: Path):
        self.root = root.resolve(strict=True)

    def artifact(self, logical_name: str) -> Path:
        allowed = "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789-_."
        if not logical_name or any(char not in allowed for char in logical_name):
            raise ValueError("invalid logical artifact name")
        candidate = (self.root / logical_name).resolve(strict=False)
        candidate.relative_to(self.root)
        return candidate


async def _bounded_cleanup(operation: Awaitable[Any], *, timeout_seconds: float = 3.0) -> bool:
    try:
        await asyncio.wait_for(operation, timeout=timeout_seconds)
        return True
    except (TimeoutError, Exception):
        return False


def _validated_payload(payload: dict[str, Any], policy: dict[str, Any]) -> tuple[str, int, int]:
    unsupported = set(payload) - {"url", "visible_text_chars", "elapsed_seconds"}
    if unsupported:
        raise ValueError("browser.inspect input contains unsupported fields")
    raw_url = payload.get("url")
    if not isinstance(raw_url, str) or not raw_url:
        raise ValueError("browser.inspect requires url")
    visible_limit = payload.get("visible_text_chars", policy["budgets"]["visible_text_chars"])
    elapsed = payload.get("elapsed_seconds", policy["budgets"]["elapsed_seconds"])
    if not isinstance(visible_limit, int) or not (1 <= visible_limit <= policy["budgets"]["visible_text_chars"]):
        raise ValueError("visible_text_chars may only tighten browser policy")
    if not isinstance(elapsed, int) or not (1 <= elapsed <= policy["budgets"]["elapsed_seconds"]):
        raise ValueError("elapsed_seconds may only tighten browser policy")
    return raw_url, visible_limit, elapsed


async def _assert_public(origin: NormalizedOrigin, resolver: Callable[..., list[tuple]]) -> tuple[str, ...]:
    return await asyncio.to_thread(assert_public_origin, origin, resolver)


def _terminal(status: str, origin: NormalizedOrigin, context_id: str, ledger: BudgetLedger, error: str) -> dict[str, Any]:
    return {
        "terminal_status": status,
        "semantic_success": False,
        "target_origin": origin.serialize(),
        "context_id": context_id,
        "budget_used": dict(ledger.used),
        "authority_transfer": False,
        "error": error,
    }


async def inspect_async(
    payload: dict[str, Any],
    *,
    resolver: Callable[..., list[tuple]] = socket.getaddrinfo,
    allow_private_fixture: bool = False,
) -> dict[str, Any]:
    policy = load_browser_policy()
    raw_url, visible_limit, elapsed = _validated_payload(payload, policy)
    allowed_origin = NormalizedOrigin.parse(raw_url)

    if policy["public_network_only"] and not allow_private_fixture:
        resolved_addresses = await _assert_public(allowed_origin, resolver)
    else:
        resolved_addresses = ("FIXTURE_PRIVATE_ALLOWED",)

    ledger = BudgetLedger.start(
        {
            "network_requests": policy["budgets"]["network_requests"],
            "pages": policy["budgets"]["pages"],
            "websockets": policy["budgets"]["websockets"],
        },
        elapsed,
    )
    ledger.consume("pages")
    context_id = f"browser-context-{uuid4()}"
    evidence = BrowserEvidence(allowed_origin.serialize(), context_id)
    blocked_event = asyncio.Event()

    try:
        from playwright.async_api import Error as PlaywrightError
        from playwright.async_api import TimeoutError as PlaywrightTimeoutError
        from playwright.async_api import async_playwright
    except ImportError as exc:
        raise BrowserRuntimeUnavailable("browser optional dependency is not installed") from exc

    playwright = None
    browser = None
    context = None
    trace_started = False
    result: dict[str, Any] | None = None
    cancelled: asyncio.CancelledError | None = None

    async def http_guard(route, request) -> None:
        try:
            ledger.consume("network_requests")
            destination = NormalizedOrigin.parse(request.url)
            if destination != allowed_origin:
                evidence.block(channel="http", url=request.url, reason="ORIGIN_NOT_ADMITTED")
                blocked_event.set()
                await route.abort("blockedbyclient")
                return
            if policy["public_network_only"] and not allow_private_fixture:
                await _assert_public(destination, resolver)
            evidence.request(method=request.method, url=request.url, resource_type=request.resource_type, allowed=allowed_origin)
            await route.continue_()
        except (BudgetExceeded, OriginValidationError):
            evidence.block(channel="http", url=request.url, reason="NETWORK_POLICY_BLOCK")
            blocked_event.set()
            await route.abort("blockedbyclient")

    async def websocket_guard(ws) -> None:
        try:
            ledger.consume("websockets")
            if not same_websocket_origin(ws.url, allowed_origin):
                evidence.block(channel="websocket", url=ws.url, reason="WEBSOCKET_ORIGIN_NOT_ADMITTED")
                blocked_event.set()
                await ws.close(code=1008, reason="origin blocked")
                return
            ws.connect_to_server()
        except BudgetExceeded:
            evidence.block(channel="websocket", url=ws.url, reason="BUDGET_EXHAUSTED")
            blocked_event.set()
            await ws.close(code=1008, reason="budget exhausted")

    with tempfile.TemporaryDirectory(prefix="aios-browser-02b-") as temp_root:
        trace_path = RunPaths(Path(temp_root)).artifact("trace.zip")
        try:
            async with asyncio.timeout(ledger.remaining_seconds()):
                playwright = await async_playwright().start()
                browser = await playwright.chromium.launch(headless=True)
                context = await browser.new_context(service_workers="block")
                await context.route("**/*", http_guard)
                await context.route_web_socket("**/*", websocket_guard)
                await context.tracing.start(screenshots=True, snapshots=True, sources=False)
                trace_started = True

                page = await context.new_page()
                page.on("console", lambda message: evidence.console_event(message.type, message.text))
                page.on("pageerror", lambda exc: evidence.page_error(str(exc)))
                context.on("response", lambda response: evidence.response(url=response.url, status=response.status))

                response = await page.goto(raw_url, wait_until="domcontentloaded")
                await asyncio.sleep(0)
                main_status = response.status if response is not None else None
                if blocked_event.is_set():
                    raise BrowserExecutionBlocked("browser network policy blocked one or more destinations")
                final_url = page.url
                if not same_http_origin(final_url, allowed_origin):
                    raise BrowserExecutionBlocked("final page origin is not admitted")

                title = await page.title()
                visible_text = await page.locator("body").inner_text()
                visible_text = visible_text[:visible_limit]
                semantic_success = main_status is not None and 200 <= main_status < 400
                result = {
                    "terminal_status": "SUCCEEDED" if semantic_success else "HTTP_ERROR",
                    "semantic_success": semantic_success,
                    "target_origin": allowed_origin.serialize(),
                    "resolved_addresses": resolved_addresses,
                    "final_url": final_url,
                    "title": title,
                    "visible_text": visible_text,
                    "main_response_status": main_status,
                    "service_workers": "block",
                    "context_id": context_id,
                    "budget_used": dict(ledger.used),
                    "authority_transfer": False,
                }
        except asyncio.CancelledError as exc:
            evidence.cancelled = True
            cancelled = exc
        except TimeoutError:
            result = _terminal("BUDGET_EXHAUSTED", allowed_origin, context_id, ledger, "elapsed browser budget exhausted")
        except BudgetExceeded as exc:
            result = _terminal("BUDGET_EXHAUSTED", allowed_origin, context_id, ledger, str(exc))
        except BrowserExecutionBlocked as exc:
            result = _terminal("TARGET_BLOCKED", allowed_origin, context_id, ledger, str(exc))
        except (PlaywrightTimeoutError, PlaywrightError) as exc:
            if blocked_event.is_set():
                result = _terminal("TARGET_BLOCKED", allowed_origin, context_id, ledger, "browser network policy blocked navigation")
            else:
                result = _terminal("FAILED", allowed_origin, context_id, ledger, f"browser execution failed: {type(exc).__name__}")
        finally:
            if context is not None:
                if trace_started:
                    trace_ok = await _bounded_cleanup(context.tracing.stop(path=str(trace_path)))
                    if trace_ok:
                        evidence.finalize_trace(trace_path)
                await _bounded_cleanup(context.close(reason="AIOS browser execution complete"))
            if browser is not None:
                await _bounded_cleanup(browser.close())
            if playwright is not None:
                await _bounded_cleanup(playwright.stop())

        if cancelled is not None:
            setattr(cancelled, "browser_evidence", evidence.to_dict())
            raise cancelled
        if result is None:
            result = _terminal("FAILED", allowed_origin, context_id, ledger, "browser execution ended without a terminal result")
        result["evidence"] = evidence.to_dict()
        return result


def run_browser_inspect(payload: dict[str, Any]) -> dict[str, Any]:
    try:
        asyncio.get_running_loop()
    except RuntimeError:
        return asyncio.run(inspect_async(payload))
    raise BrowserRuntimeUnavailable("browser.inspect sync bridge cannot run inside an active event loop")
