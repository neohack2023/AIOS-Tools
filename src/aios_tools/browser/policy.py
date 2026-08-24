from __future__ import annotations

import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[3]
BROWSER_POLICY_PATH = ROOT / "policies" / "browser-policy.v0.1.json"


class BrowserConfigurationError(RuntimeError):
    """Raised when trusted browser configuration is missing or contradictory."""


_NETWORK_EFFECTS = {
    "READ_NETWORK",
    "REMOTE_MUTATION_REVERSIBLE",
    "REMOTE_MUTATION_HIGH_IMPACT",
}
_MUTATION_EFFECTS = {
    "REMOTE_MUTATION_REVERSIBLE",
    "REMOTE_MUTATION_HIGH_IMPACT",
}


def load_browser_policy() -> dict[str, Any]:
    try:
        policy = json.loads(BROWSER_POLICY_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise BrowserConfigurationError(f"cannot load browser policy: {exc}") from exc

    required = {
        "policy_version",
        "runtime_state",
        "capability_id",
        "admitted_tools",
        "allowed_schemes",
        "read_http_methods",
        "mutation_http_methods",
        "public_network_only",
        "service_workers",
        "websocket_policy",
        "downloads",
        "download_quarantine",
        "upload_intake",
        "mutation",
        "budgets",
    }
    missing = sorted(required - policy.keys())
    if missing:
        raise BrowserConfigurationError(f"browser policy missing fields: {', '.join(missing)}")
    if policy["capability_id"] != "cap:browser-control":
        raise BrowserConfigurationError("browser capability_id is invalid")
    if policy["runtime_state"] not in {"ACTIVATION_CANDIDATE", "ACTIVE"}:
        raise BrowserConfigurationError("browser runtime_state is invalid")
    if policy["public_network_only"] is not True:
        raise BrowserConfigurationError("browser runtime must remain public-network-only")
    if policy["service_workers"] != "block":
        raise BrowserConfigurationError("browser runtime must block service workers")
    if policy["websocket_policy"] != "block":
        raise BrowserConfigurationError("browser runtime must block WebSocket connections")
    if policy["allowed_schemes"] != ["https", "http"]:
        raise BrowserConfigurationError("browser schemes must be exactly https/http")
    if policy["read_http_methods"] != ["GET", "HEAD"]:
        raise BrowserConfigurationError("browser read methods must be exactly GET/HEAD")
    if set(policy["mutation_http_methods"]) != {"POST", "PUT", "PATCH", "DELETE"}:
        raise BrowserConfigurationError("browser mutation methods must be POST/PUT/PATCH/DELETE")

    admitted = policy["admitted_tools"]
    if not isinstance(admitted, dict) or not admitted:
        raise BrowserConfigurationError("browser admitted_tools must be a non-empty object")
    inspect = admitted.get("browser.inspect")
    if inspect != {"mode": "READ_ONLY", "effect_class": "READ_NETWORK"}:
        raise BrowserConfigurationError("browser.inspect admission is invalid")
    for name, metadata in admitted.items():
        if not isinstance(name, str) or not isinstance(metadata, dict):
            raise BrowserConfigurationError("browser admitted tool entry is invalid")
        mode = metadata.get("mode")
        effect = metadata.get("effect_class")
        if effect not in _NETWORK_EFFECTS:
            raise BrowserConfigurationError(f"browser admitted tool {name} has invalid network effect class")
        if effect == "READ_NETWORK" and mode != "READ_ONLY":
            raise BrowserConfigurationError(f"browser read tool {name} must be READ_ONLY")
        if effect in _MUTATION_EFFECTS and mode != "WRITE":
            raise BrowserConfigurationError(f"browser mutation tool {name} must be WRITE")

    quarantine = policy["download_quarantine"]
    if not isinstance(quarantine, dict) or quarantine.get("status") not in {"ACTIVE_CANDIDATE", "ACTIVE"}:
        raise BrowserConfigurationError("download quarantine policy is invalid")
    uploads = policy["upload_intake"]
    if (
        not isinstance(uploads, dict)
        or uploads.get("caller_filesystem_paths") is not False
        or uploads.get("in_memory_playwright_payload") is not True
        or uploads.get("live_file_input_requires_mutation_grant") is not True
    ):
        raise BrowserConfigurationError("browser upload intake policy is invalid")
    mutation = policy["mutation"]
    if not isinstance(mutation, dict):
        raise BrowserConfigurationError("browser mutation policy is invalid")
    required_true = {
        "one_shot_approval_required",
        "exact_target_required",
        "exact_method_required",
        "idempotency_key_required",
        "post_mutation_readback_required",
        "high_impact_ack_required",
    }
    if any(mutation.get(key) is not True for key in required_true):
        raise BrowserConfigurationError("browser mutation safety requirements must remain enabled")
    if mutation.get("ambiguous_state_retry") is not False:
        raise BrowserConfigurationError("ambiguous browser mutation state may not retry")
    if mutation.get("max_redirects") != 0 or mutation.get("max_retries") != 0:
        raise BrowserConfigurationError("browser mutations must disable redirects and retries")

    for key in (
        "elapsed_seconds",
        "network_requests",
        "pages",
        "websockets",
        "visible_text_chars",
        "mutations",
        "uploads",
        "downloads",
    ):
        value = policy["budgets"].get(key)
        if not isinstance(value, int) or value <= 0:
            raise BrowserConfigurationError(f"browser budget {key} must be a positive integer")
    return policy


def browser_network_tool_admitted(tool: str, metadata: dict[str, Any]) -> bool:
    expected = load_browser_policy()["admitted_tools"].get(tool)
    return bool(
        expected
        and metadata.get("mode") == expected["mode"]
        and metadata.get("effect_class") == expected["effect_class"]
    )


def browser_runtime_active() -> bool:
    return load_browser_policy()["runtime_state"] == "ACTIVE"
