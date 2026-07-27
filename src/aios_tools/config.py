from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Callable

from jsonschema import Draft202012Validator

ROOT = Path(__file__).resolve().parents[2]
REGISTRY_PATH = ROOT / "registry" / "tools.v0.1.json"
POLICY_PATH = ROOT / "policies" / "execution-policy.v0.1.json"
REQUEST_SCHEMA_PATH = ROOT / "contracts" / "tool-request.v0.1.schema.json"


class ConfigurationError(RuntimeError):
    """Raised when governed runtime configuration is missing or contradictory."""


def _load_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ConfigurationError(f"cannot load {path.relative_to(ROOT)}: {exc}") from exc
    if not isinstance(value, dict):
        raise ConfigurationError(f"{path.relative_to(ROOT)} must contain a JSON object")
    return value


def load_policy() -> dict[str, Any]:
    policy = _load_json(POLICY_PATH)
    required = {
        "policy_version",
        "default_mode",
        "allowed_modes",
        "durable_writes_enabled",
        "external_network_effects_enabled",
        "authority_transfer_allowed",
    }
    missing = sorted(required - policy.keys())
    if missing:
        raise ConfigurationError(f"execution policy missing fields: {', '.join(missing)}")
    if not isinstance(policy["allowed_modes"], list) or not policy["allowed_modes"]:
        raise ConfigurationError("execution policy allowed_modes must be a non-empty list")
    if policy["default_mode"] not in policy["allowed_modes"]:
        raise ConfigurationError("execution policy default_mode must be globally allowed")
    if policy["durable_writes_enabled"] is not False:
        raise ConfigurationError("Slice 0 forbids durable writes")
    if policy["external_network_effects_enabled"] is not False:
        raise ConfigurationError("Slice 0 forbids external network effects")
    if policy["authority_transfer_allowed"] is not False:
        raise ConfigurationError("Slice 0 forbids authority transfer")
    return policy


def load_registry(handlers: dict[str, Callable[..., Any]]) -> tuple[dict[str, dict[str, Any]], str]:
    document = _load_json(REGISTRY_PATH)
    version = document.get("registry_version")
    tools = document.get("tools")
    if not isinstance(version, str) or not version:
        raise ConfigurationError("registry_version must be a non-empty string")
    if not isinstance(tools, list) or not tools:
        raise ConfigurationError("registry tools must be a non-empty list")

    required = {"name", "version", "mode", "reversibility", "blast_radius", "authority_transfer"}
    registry: dict[str, dict[str, Any]] = {}
    for item in tools:
        if not isinstance(item, dict):
            raise ConfigurationError("every registry tool entry must be an object")
        missing = sorted(required - item.keys())
        if missing:
            raise ConfigurationError(f"registry entry missing fields: {', '.join(missing)}")
        name = item["name"]
        if not isinstance(name, str) or not name:
            raise ConfigurationError("registry tool name must be a non-empty string")
        if name in registry:
            raise ConfigurationError(f"duplicate registry tool: {name}")
        if item["authority_transfer"] is not False:
            raise ConfigurationError(f"Slice 0 tool {name} cannot transfer authority")
        registry[name] = dict(item)

    registered = set(registry)
    bound = set(handlers)
    if registered != bound:
        missing_handlers = sorted(registered - bound)
        unregistered_handlers = sorted(bound - registered)
        details = []
        if missing_handlers:
            details.append(f"missing handlers: {', '.join(missing_handlers)}")
        if unregistered_handlers:
            details.append(f"unregistered handlers: {', '.join(unregistered_handlers)}")
        raise ConfigurationError("registry/handler mismatch; " + "; ".join(details))
    return registry, version


def validate_request(request: dict[str, Any]) -> list[str]:
    schema = _load_json(REQUEST_SCHEMA_PATH)
    errors = sorted(
        Draft202012Validator(schema).iter_errors(request),
        key=lambda error: (list(error.absolute_path), error.message),
    )
    return [error.message for error in errors]
