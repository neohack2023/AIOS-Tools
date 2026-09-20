from __future__ import annotations

import copy
from typing import Any

from .runtime import PortablePackageEvalError

TERMINAL_STATES = frozenset({"COMPLETED", "FAILED", "BLOCKED"})
ALLOWED_TRANSITIONS = {
    "NOT_EXECUTED": {"SESSION_PROVISIONING", "BLOCKED"},
    "SESSION_PROVISIONING": {"PACKAGE_ATTACHED", "FAILED", "BLOCKED"},
    "PACKAGE_ATTACHED": {"PROMPT_SUBMITTED", "FAILED", "BLOCKED"},
    "PROMPT_SUBMITTED": {"AUTH_REQUIRED", "COMPLETED", "FAILED", "BLOCKED"},
    "AUTH_REQUIRED": {"USER_TAKEOVER", "FAILED", "BLOCKED"},
    "USER_TAKEOVER": {"VERIFY_PENDING", "FAILED", "BLOCKED"},
    "VERIFY_PENDING": {"AUTOMATION_RESUMED", "FAILED", "BLOCKED"},
    "AUTOMATION_RESUMED": {"COMPLETED", "AUTH_REQUIRED", "FAILED", "BLOCKED"},
    "COMPLETED": set(),
    "FAILED": set(),
    "BLOCKED": set(),
}


def initialize_product_surface_receipt(
    *,
    plan: dict[str, Any],
    package_sha256: str,
    fixture_sha256: str,
) -> dict[str, Any]:
    if plan.get("plan_schema_version") != "0.1":
        raise PortablePackageEvalError("product-surface plan schema must be 0.1")
    lane = plan.get("lane")
    if lane not in {"NONE", "CHATGPT_TEMPORARY_UNPERSONALIZED"}:
        raise PortablePackageEvalError("unsupported product-surface lane")
    return {
        "receipt_schema_version": "0.1",
        "lane": lane,
        "state": "NOT_EXECUTED",
        "package_sha256": package_sha256,
        "fixture_sha256": fixture_sha256,
        "human_takeover_allowed": bool(
            plan.get("human_takeover", {}).get("allowed", False)
        ),
        "secret_input_model_visible": False,
        "events": [],
        "authority_transfer": False,
    }


def advance_product_surface_receipt(
    *,
    receipt: dict[str, Any],
    next_state: str,
    evidence: dict[str, Any] | None = None,
) -> dict[str, Any]:
    current = receipt.get("state")
    if current not in ALLOWED_TRANSITIONS:
        raise PortablePackageEvalError(f"unknown current product-surface state: {current}")
    if next_state not in ALLOWED_TRANSITIONS[current]:
        raise PortablePackageEvalError(
            f"invalid product-surface transition: {current} -> {next_state}"
        )
    if next_state == "USER_TAKEOVER" and not receipt.get("human_takeover_allowed"):
        raise PortablePackageEvalError("human takeover is not allowed by the plan")
    event = dict(evidence or {})
    forbidden_keys = {
        "password",
        "mfa_code",
        "captcha_answer",
        "cookie",
        "cookies",
        "storage_state",
        "takeover_token",
        "api_key",
        "authorization",
    }
    overlap = forbidden_keys & {str(key).lower() for key in event}
    if overlap:
        raise PortablePackageEvalError(
            "product-surface evidence contains forbidden secret material: "
            + ", ".join(sorted(overlap))
        )
    updated = copy.deepcopy(receipt)
    updated["events"].append({
        "from": current,
        "to": next_state,
        "evidence": event,
    })
    updated["state"] = next_state
    return updated


def validate_product_surface_receipt(receipt: dict[str, Any]) -> dict[str, Any]:
    state = receipt.get("state")
    if state not in ALLOWED_TRANSITIONS:
        raise PortablePackageEvalError("product-surface receipt has unknown state")
    if receipt.get("secret_input_model_visible") is not False:
        raise PortablePackageEvalError(
            "product-surface receipt must preserve model-invisible secret input"
        )
    if receipt.get("authority_transfer") is not False:
        raise PortablePackageEvalError(
            "product-surface receipt may not transfer authority"
        )
    events = receipt.get("events")
    if not isinstance(events, list):
        raise PortablePackageEvalError("product-surface events must be a list")

    cursor = "NOT_EXECUTED"
    for event in events:
        if not isinstance(event, dict):
            raise PortablePackageEvalError("product-surface event must be an object")
        if event.get("from") != cursor:
            raise PortablePackageEvalError("product-surface event chain is discontinuous")
        target = event.get("to")
        if target not in ALLOWED_TRANSITIONS[cursor]:
            raise PortablePackageEvalError(
                f"invalid recorded product-surface transition: {cursor} -> {target}"
            )
        cursor = target
    if cursor != state:
        raise PortablePackageEvalError(
            "product-surface receipt state does not match event chain"
        )
    return {
        "valid": True,
        "terminal": state in TERMINAL_STATES,
        "state": state,
    }
