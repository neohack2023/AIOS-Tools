from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Callable

from jsonschema import Draft202012Validator

ROOT = Path(__file__).resolve().parents[2]
REGISTRY_PATH = ROOT / "registry" / "tools.v0.1.json"
POLICY_PATH = ROOT / "policies" / "execution-policy.v0.1.json"
REQUEST_SCHEMA_PATH = ROOT / "contracts" / "tool-request.v0.1.schema.json"

EFFECT_CLASSES = frozenset(
    {
        "NO_EXTERNAL_EFFECT",
        "LOCAL_DURABLE_WRITE",
        "READ_NETWORK",
        "REMOTE_MUTATION_REVERSIBLE",
        "REMOTE_MUTATION_HIGH_IMPACT",
    }
)
NETWORK_EFFECT_CLASSES = frozenset(
    {
        "READ_NETWORK",
        "REMOTE_MUTATION_REVERSIBLE",
        "REMOTE_MUTATION_HIGH_IMPACT",
    }
)
REMOTE_MUTATION_EFFECT_CLASSES = frozenset(
    {
        "REMOTE_MUTATION_REVERSIBLE",
        "REMOTE_MUTATION_HIGH_IMPACT",
    }
)


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


def _validated_string_set(value: Any, *, field: str, allow_empty: bool = False) -> set[str]:
    if not isinstance(value, list) or (not value and not allow_empty):
        qualifier = "a list" if allow_empty else "a non-empty list"
        raise ConfigurationError(f"{field} must be {qualifier}")
    if not all(isinstance(item, str) and item for item in value):
        raise ConfigurationError(f"{field} must contain non-empty strings")
    if len(value) != len(set(value)):
        raise ConfigurationError(f"{field} must not contain duplicates")
    return set(value)


def load_policy() -> dict[str, Any]:
    policy = _load_json(POLICY_PATH)
    required = {
        "policy_version",
        "default_mode",
        "allowed_modes",
        "durable_writes_enabled",
        "external_network_effects_enabled",
        "authority_transfer_allowed",
        "approval_required_for",
        "effect_policy",
    }
    missing = sorted(required - policy.keys())
    if missing:
        raise ConfigurationError(f"execution policy missing fields: {', '.join(missing)}")
    if not isinstance(policy["allowed_modes"], list) or not policy["allowed_modes"]:
        raise ConfigurationError("execution policy allowed_modes must be a non-empty list")
    if policy["default_mode"] not in policy["allowed_modes"]:
        raise ConfigurationError("execution policy default_mode must be globally allowed")
    if not isinstance(policy["durable_writes_enabled"], bool):
        raise ConfigurationError("execution policy durable_writes_enabled must be boolean")
    if policy["external_network_effects_enabled"] is not False:
        raise ConfigurationError("external network effects must remain disabled")
    if policy["authority_transfer_allowed"] is not False:
        raise ConfigurationError("authority transfer must remain disabled")
    if not isinstance(policy["approval_required_for"], list):
        raise ConfigurationError("approval_required_for must be a list")
    if "WRITE" in policy["allowed_modes"]:
        if policy["durable_writes_enabled"] is not True:
            raise ConfigurationError("WRITE mode requires durable_writes_enabled=true")
        if "WRITE" not in policy["approval_required_for"]:
            raise ConfigurationError("WRITE mode requires explicit approval")
        if policy.get("write_scope") != "LOCAL_ARTIFACTS_ONLY":
            raise ConfigurationError("WRITE mode is limited to LOCAL_ARTIFACTS_ONLY")
    elif policy["durable_writes_enabled"] is not False:
        raise ConfigurationError("durable writes cannot be enabled when WRITE mode is absent")

    effect_policy = policy["effect_policy"]
    if not isinstance(effect_policy, dict):
        raise ConfigurationError("execution policy effect_policy must be an object")
    effect_required = {
        "known_effect_classes",
        "allowed_effect_classes",
        "network_effect_classes",
        "remote_mutation_effect_classes",
    }
    effect_missing = sorted(effect_required - effect_policy.keys())
    if effect_missing:
        raise ConfigurationError(f"effect_policy missing fields: {', '.join(effect_missing)}")

    known = _validated_string_set(effect_policy["known_effect_classes"], field="effect_policy known_effect_classes")
    allowed = _validated_string_set(
        effect_policy["allowed_effect_classes"],
        field="effect_policy allowed_effect_classes",
        allow_empty=True,
    )
    network = _validated_string_set(effect_policy["network_effect_classes"], field="effect_policy network_effect_classes")
    remote = _validated_string_set(
        effect_policy["remote_mutation_effect_classes"],
        field="effect_policy remote_mutation_effect_classes",
    )

    if known != EFFECT_CLASSES:
        raise ConfigurationError("effect_policy known_effect_classes must match the runtime effect taxonomy")
    if network != NETWORK_EFFECT_CLASSES:
        raise ConfigurationError("effect_policy network_effect_classes must match the runtime network taxonomy")
    if remote != REMOTE_MUTATION_EFFECT_CLASSES:
        raise ConfigurationError("effect_policy remote_mutation_effect_classes must match the runtime mutation taxonomy")
    if not allowed <= known:
        raise ConfigurationError("effect_policy allowed_effect_classes must be a subset of known_effect_classes")
    if not remote <= network:
        raise ConfigurationError("remote mutation effect classes must also be network effect classes")
    if allowed & network:
        raise ConfigurationError("network effect classes cannot be admitted while external network effects are disabled")

    return policy


def load_registry(handlers: dict[str, Callable[..., Any]]) -> tuple[dict[str, dict[str, Any]], str]:
    document = _load_json(REGISTRY_PATH)
    version = document.get("registry_version")
    tools = document.get("tools")
    if not isinstance(version, str) or not version:
        raise ConfigurationError("registry_version must be a non-empty string")
    if not isinstance(tools, list) or not tools:
        raise ConfigurationError("registry tools must be a non-empty list")

    required = {"name", "version", "mode", "effect_class", "reversibility", "blast_radius", "authority_transfer"}
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
            raise ConfigurationError(f"tool {name} cannot transfer authority")

        effect_class = item["effect_class"]
        if effect_class not in EFFECT_CLASSES:
            raise ConfigurationError(f"tool {name} has unknown effect_class: {effect_class}")
        mode = item["mode"]
        if effect_class == "NO_EXTERNAL_EFFECT" and mode == "WRITE":
            raise ConfigurationError(f"tool {name} cannot declare NO_EXTERNAL_EFFECT in WRITE mode")
        if effect_class == "LOCAL_DURABLE_WRITE" and mode != "WRITE":
            raise ConfigurationError(f"tool {name} LOCAL_DURABLE_WRITE requires WRITE mode")
        if effect_class == "READ_NETWORK" and mode != "READ_ONLY":
            raise ConfigurationError(f"tool {name} READ_NETWORK requires READ_ONLY mode")
        if effect_class in REMOTE_MUTATION_EFFECT_CLASSES and mode != "WRITE":
            raise ConfigurationError(f"tool {name} remote mutation effect requires WRITE mode")

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
