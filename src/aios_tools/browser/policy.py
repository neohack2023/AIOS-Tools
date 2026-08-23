from __future__ import annotations

import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[3]
BROWSER_POLICY_PATH = ROOT / "policies" / "browser-policy.v0.1.json"


class BrowserConfigurationError(RuntimeError):
    """Raised when trusted browser configuration is missing or contradictory."""


def load_browser_policy() -> dict[str, Any]:
    try:
        policy = json.loads(BROWSER_POLICY_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise BrowserConfigurationError(f"cannot load browser policy: {exc}") from exc

    required = {
        "policy_version", "capability_id", "effect_class", "admitted_tools",
        "allowed_schemes", "allowed_http_methods", "public_network_only",
        "service_workers", "websocket_policy", "downloads", "budgets",
    }
    missing = sorted(required - policy.keys())
    if missing:
        raise BrowserConfigurationError(f"browser policy missing fields: {', '.join(missing)}")
    if policy["capability_id"] != "cap:browser-control":
        raise BrowserConfigurationError("browser capability_id is invalid")
    if policy["effect_class"] != "READ_NETWORK":
        raise BrowserConfigurationError("02B must remain READ_NETWORK")
    if policy["public_network_only"] is not True:
        raise BrowserConfigurationError("02B must remain public-network-only")
    if policy["service_workers"] != "block":
        raise BrowserConfigurationError("02B must block service workers")
    if policy["websocket_policy"] != "block":
        raise BrowserConfigurationError("02B must block WebSocket connections")
    if policy["downloads"] != "block":
        raise BrowserConfigurationError("02B must block downloads")
    if policy["allowed_schemes"] != ["https", "http"]:
        raise BrowserConfigurationError("02B schemes must be exactly https/http")
    if policy["allowed_http_methods"] != ["GET", "HEAD"]:
        raise BrowserConfigurationError("02B HTTP methods must be exactly GET/HEAD")
    expected_tools = {"browser.inspect": {"mode": "READ_ONLY", "effect_class": "READ_NETWORK"}}
    if policy["admitted_tools"] != expected_tools:
        raise BrowserConfigurationError("02B admitted browser tool set is invalid")
    for key in ("elapsed_seconds", "network_requests", "pages", "websockets", "visible_text_chars"):
        value = policy["budgets"].get(key)
        if not isinstance(value, int) or value <= 0:
            raise BrowserConfigurationError(f"browser budget {key} must be a positive integer")
    return policy


def browser_network_tool_admitted(tool: str, metadata: dict[str, Any]) -> bool:
    expected = load_browser_policy()["admitted_tools"].get(tool)
    return bool(expected and metadata.get("mode") == expected["mode"] and metadata.get("effect_class") == expected["effect_class"])
