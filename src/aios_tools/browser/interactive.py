from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from hashlib import sha256
import socket
import re
from threading import Event, Lock, Thread
from time import monotonic, time
from typing import Any, Coroutine
from urllib.parse import urljoin, urlsplit
from uuid import uuid4

from .budget import BudgetExceeded, BudgetLedger
from .evidence import BrowserEvidence, minimize_url
from .origin import NormalizedOrigin, OriginValidationError, assert_public_origin
from .policy import load_browser_policy


class InteractiveBrowserError(RuntimeError):
    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code


_RISK_TERMS = {
    "buy",
    "checkout",
    "confirm",
    "create",
    "delete",
    "follow",
    "like",
    "log out",
    "logout",
    "order",
    "pay",
    "publish",
    "purchase",
    "remove",
    "save",
    "send",
    "sign out",
    "submit",
    "subscribe",
    "unfollow",
    "unsubscribe",
    "update",
    "upload",
}
_SAFE_KEYS = {
    "ArrowDown",
    "ArrowLeft",
    "ArrowRight",
    "ArrowUp",
    "End",
    "Escape",
    "Home",
    "PageDown",
    "PageUp",
    "Shift+Tab",
    "Tab",
}


def _url_crosses_risk_boundary(raw_url: str) -> bool:
    parsed = urlsplit(raw_url)
    raw_target = (parsed.path + "?" + parsed.query).lower()
    tokens = {token for token in re.split(r"[^a-z0-9]+", raw_target) if token}
    compact_risks = {term.replace(" ", "") for term in _RISK_TERMS}
    return bool(tokens & compact_risks) or any(
        phrase in raw_target
        for phrase in ("sign-out", "sign_out", "log-out", "log_out")
    )


def _digest(value: str) -> str:
    return "sha256:" + sha256(value.encode("utf-8")).hexdigest()


def _terminal(code: str, message: str, *, session_id: str | None = None) -> dict[str, Any]:
    return {
        "terminal_status": code,
        "semantic_success": False,
        "session_id": session_id,
        "authority_transfer": False,
        "error": message,
    }


def _validate_session_id(value: Any) -> str:
    if not isinstance(value, str) or not value.startswith("browser-session-") or len(value) > 96:
        raise ValueError("interactive browser session_id is invalid")
    return value


def _validate_positive_int(value: Any, *, name: str, maximum: int) -> int:
    if not isinstance(value, int) or isinstance(value, bool) or not (1 <= value <= maximum):
        raise ValueError(f"{name} must be an integer from 1 to {maximum}")
    return value


@dataclass(slots=True)
class InteractiveSession:
    session_id: str
    origin: NormalizedOrigin
    resource_origins: frozenset[NormalizedOrigin]
    created_at: float
    expires_at: float
    ledger: BudgetLedger
    evidence: BrowserEvidence
    context: Any
    page: Any
    element_refs: dict[str, Any] = field(default_factory=dict)
    observation_generation: int = 0
    fatal_reason: str | None = None


class InteractiveBrowserService:
    """Own Playwright objects on one dedicated event-loop thread.

    MCP transport sessions may be stateless, but the server process remains the
    runtime boundary. Browser session identifiers are therefore deliberately
    process-local and become invalid after a restart.
    """

    def __init__(self) -> None:
        self._start_lock = Lock()
        self._ready = Event()
        self._thread: Thread | None = None
        self._loop: asyncio.AbstractEventLoop | None = None
        self._playwright_manager: Any = None
        self._browser: Any = None
        self._sessions: dict[str, InteractiveSession] = {}
        self._expiry_tasks: set[asyncio.Task[Any]] = set()

    def _ensure_thread(self) -> None:
        if self._thread is not None and self._thread.is_alive():
            return
        with self._start_lock:
            if self._thread is not None and self._thread.is_alive():
                return
            self._ready.clear()

            def run() -> None:
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                self._loop = loop
                self._ready.set()
                loop.run_forever()
                loop.close()

            self._thread = Thread(target=run, name="aios-browser-interactive", daemon=True)
            self._thread.start()
            if not self._ready.wait(timeout=5):
                raise InteractiveBrowserError("RUNTIME_UNAVAILABLE", "interactive browser event loop did not start")

    def _call(self, coroutine: Coroutine[Any, Any, dict[str, Any]], *, timeout: float = 75.0) -> dict[str, Any]:
        self._ensure_thread()
        if self._loop is None:
            coroutine.close()
            raise InteractiveBrowserError("RUNTIME_UNAVAILABLE", "interactive browser event loop is unavailable")
        future = asyncio.run_coroutine_threadsafe(coroutine, self._loop)
        try:
            return future.result(timeout=timeout)
        except TimeoutError as exc:
            future.cancel()
            raise InteractiveBrowserError("BUDGET_EXHAUSTED", "interactive browser command timed out") from exc

    async def _ensure_browser(self) -> Any:
        if self._browser is not None:
            return self._browser
        try:
            from playwright.async_api import async_playwright
        except ImportError as exc:
            raise InteractiveBrowserError("RUNTIME_UNAVAILABLE", "browser optional dependency is not installed") from exc
        self._playwright_manager = async_playwright()
        playwright = await self._playwright_manager.start()
        self._browser = await playwright.chromium.launch(headless=True)
        return self._browser

    async def _close_session(self, session: InteractiveSession) -> None:
        self._sessions.pop(session.session_id, None)
        try:
            await session.context.close(reason="AIOS interactive session closed")
        except Exception:
            pass

    async def _expire_later(self, session_id: str, delay: float) -> None:
        await asyncio.sleep(delay)
        session = self._sessions.get(session_id)
        if session is not None and monotonic() >= session.ledger.deadline:
            await self._close_session(session)

    def _schedule_expiry(self, session: InteractiveSession) -> None:
        task = asyncio.create_task(
            self._expire_later(session.session_id, max(0.0, session.ledger.remaining_seconds()))
        )
        self._expiry_tasks.add(task)
        task.add_done_callback(self._expiry_tasks.discard)

    async def _purge_expired(self) -> None:
        for session in list(self._sessions.values()):
            if monotonic() >= session.ledger.deadline:
                await self._close_session(session)

    async def _get_session(self, session_id: str) -> InteractiveSession:
        session = self._sessions.get(session_id)
        if session is None:
            raise InteractiveBrowserError("SESSION_NOT_FOUND", "interactive browser session is unavailable")
        if monotonic() >= session.ledger.deadline:
            await self._close_session(session)
            raise InteractiveBrowserError("SESSION_EXPIRED", "interactive browser session expired")
        if session.fatal_reason is not None:
            await self._close_session(session)
            raise InteractiveBrowserError("SESSION_BLOCKED", session.fatal_reason)
        return session

    @staticmethod
    def _evidence_delta(session: InteractiveSession, cursors: tuple[int, int, int, int]) -> dict[str, Any]:
        network, console, errors, blocked = cursors
        return {
            "target_origin": session.origin.serialize(),
            "context_id": session.session_id,
            "network": list(session.evidence.network[network:]),
            "console": list(session.evidence.console[console:]),
            "page_errors": list(session.evidence.page_errors[errors:]),
            "blocked": list(session.evidence.blocked[blocked:]),
            "trace_digest": None,
            "cancelled": False,
        }

    @staticmethod
    def _evidence_cursors(session: InteractiveSession) -> tuple[int, int, int, int]:
        return (
            len(session.evidence.network),
            len(session.evidence.console),
            len(session.evidence.page_errors),
            len(session.evidence.blocked),
        )

    async def _observe(
        self,
        session: InteractiveSession,
        *,
        visible_text_chars: int,
        max_elements: int,
    ) -> dict[str, Any]:
        session.ledger.consume("observations")
        session.observation_generation += 1
        session.element_refs.clear()
        title = await session.page.title()
        try:
            visible_text = await session.page.locator("body").inner_text(timeout=5000)
        except Exception:
            visible_text = ""
        visible_text = visible_text[:visible_text_chars]
        candidates = session.page.locator(
            'a[href],button,input:not([type="hidden"]),textarea,select,'
            '[role="button"],[role="link"],[role="tab"]'
        )
        elements: list[dict[str, Any]] = []
        count = min(await candidates.count(), max_elements * 4)
        for index in range(count):
            if len(elements) >= max_elements:
                break
            item = candidates.nth(index)
            try:
                if not await item.is_visible():
                    continue
                role = await item.get_attribute("role")
                input_type = await item.get_attribute("type")
                aria_label = await item.get_attribute("aria-label")
                placeholder = await item.get_attribute("placeholder")
                title_attr = await item.get_attribute("title")
                href = await item.get_attribute("href")
                text = (await item.inner_text(timeout=1000)).strip()
            except Exception:
                continue
            name = (aria_label or text or placeholder or title_attr or "")[:240]
            ref = f"g{session.observation_generation}-e{len(elements) + 1}"
            session.element_refs[ref] = item
            record: dict[str, Any] = {
                "element_ref": ref,
                "role": role,
                "name": name,
                "input_type": input_type,
            }
            if href:
                resolved = urljoin(session.page.url, href)
                try:
                    summary = minimize_url(resolved)
                except Exception:
                    summary = None
                record["link_target"] = summary
            elements.append(record)
        final = minimize_url(session.page.url)
        return {
            "observation_generation": session.observation_generation,
            "title": title,
            "current_origin": final["origin"],
            "current_path_digest": final["path_digest"],
            "visible_text": visible_text,
            "interactive_elements": elements,
            "untrusted_page_data": True,
            "instruction_authority": False,
            "form_values_recorded": False,
        }

    async def _open(self, payload: dict[str, Any], *, allow_private_fixture: bool = False) -> dict[str, Any]:
        policy = load_browser_policy()
        allowed = {"url", "resource_origins", "session_seconds", "visible_text_chars", "max_elements"}
        unsupported = set(payload) - allowed
        if unsupported:
            raise ValueError("browser.session.open contains unsupported fields")
        raw_url = payload.get("url")
        if not isinstance(raw_url, str) or not raw_url:
            raise ValueError("browser.session.open requires url")
        try:
            origin = NormalizedOrigin.parse(raw_url)
        except OriginValidationError as exc:
            raise InteractiveBrowserError("TARGET_BLOCKED", "browser target is not admitted") from exc
        raw_resources = payload.get("resource_origins", [])
        if not isinstance(raw_resources, list) or len(raw_resources) > 8 or not all(isinstance(item, str) for item in raw_resources):
            raise ValueError("resource_origins must contain at most eight origins")
        try:
            resources = frozenset(NormalizedOrigin.parse(item) for item in raw_resources)
        except OriginValidationError as exc:
            raise ValueError("resource_origins contains an invalid origin") from exc
        if origin in resources:
            resources = frozenset(item for item in resources if item != origin)
        if policy["public_network_only"] and not allow_private_fixture:
            try:
                await asyncio.to_thread(assert_public_origin, origin, socket.getaddrinfo)
                for resource in resources:
                    await asyncio.to_thread(assert_public_origin, resource, socket.getaddrinfo)
            except OriginValidationError as exc:
                raise InteractiveBrowserError("TARGET_BLOCKED", "browser target is not admitted") from exc
        interactive = policy["interactive"]
        await self._purge_expired()
        if len(self._sessions) >= interactive["max_sessions"]:
            raise InteractiveBrowserError("BUDGET_EXHAUSTED", "interactive browser session capacity is exhausted")
        session_seconds = _validate_positive_int(
            payload.get("session_seconds", interactive["session_seconds"]),
            name="session_seconds",
            maximum=interactive["session_seconds"],
        )
        visible_text_chars = _validate_positive_int(
            payload.get("visible_text_chars", interactive["visible_text_chars"]),
            name="visible_text_chars",
            maximum=interactive["visible_text_chars"],
        )
        max_elements = _validate_positive_int(
            payload.get("max_elements", interactive["max_elements"]),
            name="max_elements",
            maximum=interactive["max_elements"],
        )
        browser = await self._ensure_browser()
        context = await browser.new_context(service_workers="block", accept_downloads=False)
        page = await context.new_page()
        session_id = "browser-session-" + uuid4().hex
        evidence = BrowserEvidence(origin.serialize(), session_id)
        ledger = BudgetLedger.start(
            {
                "network_requests": interactive["network_requests"],
                "pages": 1,
                "actions": interactive["actions"],
                "observations": interactive["observations"],
            },
            session_seconds,
        )
        session = InteractiveSession(
            session_id=session_id,
            origin=origin,
            resource_origins=resources,
            created_at=time(),
            expires_at=time() + session_seconds,
            ledger=ledger,
            evidence=evidence,
            context=context,
            page=page,
        )

        async def route_guard(route: Any, request: Any) -> None:
            try:
                session.ledger.consume("network_requests")
                method = request.method.upper()
                if method not in policy["read_http_methods"]:
                    session.evidence.block(channel="http", url=request.url, reason="HTTP_METHOD_NOT_ADMITTED")
                    session.fatal_reason = "interactive session attempted a non-read network method"
                    await route.abort("blockedbyclient")
                    return
                destination = NormalizedOrigin.parse(request.url)
                if destination != session.origin and destination not in session.resource_origins:
                    session.evidence.block(channel="http", url=request.url, reason="ORIGIN_NOT_ADMITTED")
                    if request.resource_type == "document":
                        session.fatal_reason = "interactive session attempted cross-origin document navigation"
                    await route.abort("blockedbyclient")
                    return
                if request.resource_type in {"document", "fetch", "xhr"} and _url_crosses_risk_boundary(request.url):
                    session.evidence.block(channel="http", url=request.url, reason="RISK_TARGET_NOT_ADMITTED")
                    session.fatal_reason = "interactive session reached a high-risk target"
                    await route.abort("blockedbyclient")
                    return
                if policy["public_network_only"] and not allow_private_fixture:
                    await asyncio.to_thread(assert_public_origin, destination, socket.getaddrinfo)
                session.evidence.request(method=method, url=request.url, resource_type=request.resource_type, allowed=session.origin)
                await route.continue_()
            except (BudgetExceeded, OriginValidationError):
                session.evidence.block(channel="http", url=request.url, reason="NETWORK_POLICY_BLOCK")
                session.fatal_reason = "interactive browser network policy blocked the session"
                await route.abort("blockedbyclient")

        async def websocket_guard(websocket: Any) -> None:
            session.evidence.block(channel="websocket", url=websocket.url, reason="WEBSOCKET_DISABLED_IN_INTERACTIVE_READ")
            await websocket.close(code=1008, reason="read-only interactive browser blocks WebSockets")

        def popup_guard(popup: Any) -> None:
            session.evidence.block(channel="page", url=popup.url or "about:blank", reason="POPUP_DISABLED_IN_INTERACTIVE_READ")
            session.fatal_reason = "interactive browser popup was blocked"
            asyncio.create_task(popup.close())

        def download_guard(download: Any) -> None:
            session.evidence.block(channel="download", url=download.url, reason="DOWNLOAD_DISABLED_IN_INTERACTIVE_READ")
            session.fatal_reason = "interactive browser download was blocked"

        await context.route("**/*", route_guard)
        await context.route_web_socket("**/*", websocket_guard)
        context.on("page", popup_guard)
        page.on("download", download_guard)
        page.on("console", lambda message: session.evidence.console_event(message.type, message.text))
        page.on("pageerror", lambda error: session.evidence.page_error(str(error)))
        context.on("response", lambda response: session.evidence.response(url=response.url, status=response.status))
        cursors = self._evidence_cursors(session)
        try:
            response = await page.goto(raw_url, wait_until="domcontentloaded", timeout=min(30000, session_seconds * 1000))
            await asyncio.sleep(0)
            if session.fatal_reason is not None:
                raise InteractiveBrowserError("TARGET_BLOCKED", session.fatal_reason)
            if NormalizedOrigin.parse(page.url) != origin:
                raise InteractiveBrowserError("TARGET_BLOCKED", "final browser origin is not admitted")
            observation = await self._observe(
                session,
                visible_text_chars=visible_text_chars,
                max_elements=max_elements,
            )
            self._sessions[session_id] = session
            self._schedule_expiry(session)
            status = response.status if response is not None else None
            return {
                "terminal_status": "SUCCEEDED" if status is not None and 200 <= status < 400 else "HTTP_ERROR",
                "semantic_success": bool(status is not None and 200 <= status < 400),
                "session_id": session_id,
                "target_origin": origin.serialize(),
                "expires_at_epoch": session.expires_at,
                "main_response_status": status,
                "observation": observation,
                "budget_used": dict(session.ledger.used),
                "evidence": self._evidence_delta(session, cursors),
                "authority_transfer": False,
            }
        except Exception:
            await self._close_session(session)
            raise

    async def _observe_command(self, payload: dict[str, Any]) -> dict[str, Any]:
        if set(payload) - {"session_id", "visible_text_chars", "max_elements"}:
            raise ValueError("browser.session.observe contains unsupported fields")
        session_id = _validate_session_id(payload.get("session_id"))
        session = await self._get_session(session_id)
        interactive = load_browser_policy()["interactive"]
        visible_text_chars = _validate_positive_int(
            payload.get("visible_text_chars", interactive["visible_text_chars"]),
            name="visible_text_chars",
            maximum=interactive["visible_text_chars"],
        )
        max_elements = _validate_positive_int(
            payload.get("max_elements", interactive["max_elements"]),
            name="max_elements",
            maximum=interactive["max_elements"],
        )
        cursors = self._evidence_cursors(session)
        try:
            observation = await self._observe(session, visible_text_chars=visible_text_chars, max_elements=max_elements)
        except BudgetExceeded as exc:
            await self._close_session(session)
            result = _terminal("BUDGET_EXHAUSTED", str(exc), session_id=session_id)
            result.update(
                target_origin=session.origin.serialize(),
                budget_used=dict(session.ledger.used),
                evidence=self._evidence_delta(session, cursors),
            )
            return result
        return {
            "terminal_status": "SUCCEEDED",
            "semantic_success": True,
            "session_id": session_id,
            "target_origin": session.origin.serialize(),
            "observation": observation,
            "budget_used": dict(session.ledger.used),
            "evidence": self._evidence_delta(session, cursors),
            "authority_transfer": False,
        }

    @staticmethod
    async def _resolve_element(session: InteractiveSession, action: dict[str, Any]) -> Any:
        ref = action.get("element_ref")
        if not isinstance(ref, str) or ref not in session.element_refs:
            raise InteractiveBrowserError("ELEMENT_REF_STALE", "action requires an element_ref from the latest observation")
        locator = session.element_refs[ref]
        if await locator.count() != 1 or not await locator.is_visible():
            raise InteractiveBrowserError("ELEMENT_REF_STALE", "interactive element is no longer uniquely available")
        return locator

    @staticmethod
    async def _assert_safe_activation(session: InteractiveSession, locator: Any) -> None:
        name = " ".join(
            filter(
                None,
                [
                    await locator.get_attribute("aria-label"),
                    await locator.get_attribute("title"),
                    (await locator.inner_text(timeout=1000)).strip(),
                ],
            )
        ).lower()
        if any(term in name for term in _RISK_TERMS):
            raise InteractiveBrowserError("ACTION_BLOCKED", "control appears to cross a remote-effect boundary")
        href = await locator.get_attribute("href")
        if href:
            destination = urljoin(session.page.url, href)
            try:
                destination_origin = NormalizedOrigin.parse(destination)
            except OriginValidationError as exc:
                raise InteractiveBrowserError("ACTION_BLOCKED", "link target is not an admitted HTTP origin") from exc
            if destination_origin != session.origin:
                raise InteractiveBrowserError("ACTION_BLOCKED", "cross-origin link activation is not admitted")
            if _url_crosses_risk_boundary(destination):
                raise InteractiveBrowserError("ACTION_BLOCKED", "link path appears to cross a remote-effect boundary")
            return
        control_type = (await locator.get_attribute("type") or "").lower()
        role = (await locator.get_attribute("role") or "").lower()
        if control_type != "button" and role not in {"button", "tab"}:
            raise InteractiveBrowserError("ACTION_BLOCKED", "read-only activation requires a link or non-submit button")

    async def _execute_action(self, session: InteractiveSession, action: dict[str, Any]) -> None:
        if not isinstance(action, dict):
            raise ValueError("each interactive browser action must be an object")
        action_type = action.get("type")
        allowed_fields = {
            "click": {"type", "element_ref"},
            "fill": {"type", "element_ref", "value"},
            "press": {"type", "element_ref", "key"},
            "select": {"type", "element_ref", "value"},
            "scroll": {"type", "delta_y"},
            "navigate": {"type", "url"},
            "back": {"type"},
            "wait": {"type", "milliseconds"},
        }
        if action_type not in allowed_fields:
            raise ValueError("unsupported interactive browser action type")
        if set(action) != allowed_fields[action_type]:
            raise ValueError(f"interactive browser {action_type} action fields are invalid")
        session.ledger.consume("actions")
        if action_type == "click":
            locator = await self._resolve_element(session, action)
            await self._assert_safe_activation(session, locator)
            await locator.click(timeout=10000)
        elif action_type == "fill":
            locator = await self._resolve_element(session, action)
            input_type = (await locator.get_attribute("type") or "text").lower()
            if input_type in {"password", "hidden", "file"}:
                raise InteractiveBrowserError("SECRET_FIELD_BLOCKED", "secret and file fields are not admitted")
            value = action.get("value")
            if not isinstance(value, str) or len(value) > 1000:
                raise ValueError("fill value must be a string of at most 1000 characters")
            await locator.fill(value, timeout=10000)
        elif action_type == "press":
            locator = await self._resolve_element(session, action)
            key = action.get("key")
            if key not in _SAFE_KEYS:
                raise InteractiveBrowserError("ACTION_BLOCKED", "keypress is not admitted by the read-only key policy")
            await locator.press(key, timeout=10000)
        elif action_type == "select":
            locator = await self._resolve_element(session, action)
            value = action.get("value")
            if not isinstance(value, str) or len(value) > 512:
                raise ValueError("select value must be a string of at most 512 characters")
            await locator.select_option(value=value, timeout=10000)
        elif action_type == "scroll":
            delta = action.get("delta_y")
            if not isinstance(delta, int) or isinstance(delta, bool) or not (-2000 <= delta <= 2000) or delta == 0:
                raise ValueError("scroll delta_y must be a non-zero integer from -2000 to 2000")
            await session.page.mouse.wheel(0, delta)
        elif action_type == "navigate":
            raw_url = action.get("url")
            try:
                destination_origin = NormalizedOrigin.parse(raw_url) if isinstance(raw_url, str) else None
            except OriginValidationError:
                destination_origin = None
            if destination_origin != session.origin:
                raise InteractiveBrowserError("ACTION_BLOCKED", "navigation must remain on the admitted origin")
            await session.page.goto(raw_url, wait_until="domcontentloaded", timeout=30000)
        elif action_type == "back":
            await session.page.go_back(wait_until="domcontentloaded", timeout=30000)
            try:
                current_origin = NormalizedOrigin.parse(session.page.url)
            except OriginValidationError:
                current_origin = None
            if current_origin != session.origin:
                raise InteractiveBrowserError("ACTION_BLOCKED", "history navigation left the admitted origin")
        else:
            milliseconds = action.get("milliseconds")
            if not isinstance(milliseconds, int) or isinstance(milliseconds, bool) or not (1 <= milliseconds <= 3000):
                raise ValueError("wait milliseconds must be an integer from 1 to 3000")
            await asyncio.sleep(milliseconds / 1000)
        await asyncio.sleep(0.05)
        if session.fatal_reason is not None:
            raise InteractiveBrowserError("SESSION_BLOCKED", session.fatal_reason)

    async def _act(self, payload: dict[str, Any]) -> dict[str, Any]:
        if set(payload) != {"session_id", "actions"}:
            raise ValueError("browser.session.act requires session_id and actions")
        session_id = _validate_session_id(payload.get("session_id"))
        session = await self._get_session(session_id)
        actions = payload.get("actions")
        batch_limit = load_browser_policy()["interactive"]["action_batch"]
        if not isinstance(actions, list) or not (1 <= len(actions) <= batch_limit):
            raise ValueError(f"actions must contain 1 to {batch_limit} typed actions")
        cursors = self._evidence_cursors(session)
        completed = 0
        try:
            for action in actions:
                await self._execute_action(session, action)
                completed += 1
            interactive = load_browser_policy()["interactive"]
            observation = await self._observe(
                session,
                visible_text_chars=interactive["visible_text_chars"],
                max_elements=interactive["max_elements"],
            )
            return {
                "terminal_status": "SUCCEEDED",
                "semantic_success": True,
                "session_id": session_id,
                "target_origin": session.origin.serialize(),
                "actions_completed": completed,
                "observation": observation,
                "budget_used": dict(session.ledger.used),
                "evidence": self._evidence_delta(session, cursors),
                "authority_transfer": False,
            }
        except (InteractiveBrowserError, BudgetExceeded) as exc:
            code = exc.code if isinstance(exc, InteractiveBrowserError) else "BUDGET_EXHAUSTED"
            if code in {"SESSION_BLOCKED", "TARGET_BLOCKED", "BUDGET_EXHAUSTED"}:
                await self._close_session(session)
            result = _terminal(code, str(exc), session_id=session_id)
            result.update(
                target_origin=session.origin.serialize(),
                actions_completed=completed,
                budget_used=dict(session.ledger.used),
                evidence=self._evidence_delta(session, cursors),
            )
            return result

    async def _close(self, payload: dict[str, Any]) -> dict[str, Any]:
        if set(payload) != {"session_id"}:
            raise ValueError("browser.session.close requires only session_id")
        session_id = _validate_session_id(payload.get("session_id"))
        session = self._sessions.get(session_id)
        if session is None:
            return _terminal("SESSION_NOT_FOUND", "interactive browser session is unavailable", session_id=session_id)
        target_origin = session.origin.serialize()
        budget_used = dict(session.ledger.used)
        await self._close_session(session)
        return {
            "terminal_status": "SUCCEEDED",
            "semantic_success": True,
            "session_id": session_id,
            "target_origin": target_origin,
            "budget_used": budget_used,
            "closed": True,
            "authority_transfer": False,
        }

    async def _shutdown(self) -> dict[str, Any]:
        for task in list(self._expiry_tasks):
            task.cancel()
        if self._expiry_tasks:
            await asyncio.gather(*list(self._expiry_tasks), return_exceptions=True)
        self._expiry_tasks.clear()
        for session in list(self._sessions.values()):
            await self._close_session(session)
        if self._browser is not None:
            try:
                await self._browser.close()
            except Exception:
                pass
            self._browser = None
        if self._playwright_manager is not None:
            try:
                await self._playwright_manager.__aexit__(None, None, None)
            except Exception:
                pass
            self._playwright_manager = None
        return {"terminal_status": "SUCCEEDED", "authority_transfer": False}

    def open(self, payload: dict[str, Any], *, allow_private_fixture: bool = False) -> dict[str, Any]:
        return self._call(self._open(payload, allow_private_fixture=allow_private_fixture))

    def observe(self, payload: dict[str, Any]) -> dict[str, Any]:
        return self._call(self._observe_command(payload))

    def act(self, payload: dict[str, Any]) -> dict[str, Any]:
        return self._call(self._act(payload))

    def close(self, payload: dict[str, Any]) -> dict[str, Any]:
        return self._call(self._close(payload))

    def shutdown(self) -> None:
        if self._thread is None or not self._thread.is_alive():
            return
        self._call(self._shutdown())
        if self._loop is not None:
            self._loop.call_soon_threadsafe(self._loop.stop)
        self._thread.join(timeout=5)
        self._thread = None
        self._loop = None


_SERVICE = InteractiveBrowserService()


def run_interactive_open(payload: dict[str, Any]) -> dict[str, Any]:
    try:
        return _SERVICE.open(payload)
    except InteractiveBrowserError as exc:
        return _terminal(exc.code, str(exc))


def run_interactive_observe(payload: dict[str, Any]) -> dict[str, Any]:
    try:
        return _SERVICE.observe(payload)
    except InteractiveBrowserError as exc:
        return _terminal(exc.code, str(exc), session_id=payload.get("session_id"))


def run_interactive_act(payload: dict[str, Any]) -> dict[str, Any]:
    try:
        return _SERVICE.act(payload)
    except InteractiveBrowserError as exc:
        return _terminal(exc.code, str(exc), session_id=payload.get("session_id"))


def run_interactive_close(payload: dict[str, Any]) -> dict[str, Any]:
    try:
        return _SERVICE.close(payload)
    except InteractiveBrowserError as exc:
        return _terminal(exc.code, str(exc), session_id=payload.get("session_id"))


def shutdown_interactive_runtime() -> None:
    _SERVICE.shutdown()
