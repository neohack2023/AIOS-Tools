from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum
from hashlib import sha256
from typing import Iterable


class GateVerdict(str, Enum):
    ALLOW = "ALLOW"
    DENY = "DENY"
    STALE = "STALE"
    UNRESOLVED = "UNRESOLVED"


@dataclass(frozen=True)
class GateDecision:
    verdict: GateVerdict
    reason: str


def digest_text(value: str) -> str:
    return sha256(value.encode("utf-8")).hexdigest()


def resolve_instruction_source(
    *,
    files: Iterable[str],
    provider_supported: bool,
    expected_digest: str | None = None,
    observed_content: str | None = None,
) -> GateDecision:
    names = set(files)
    if not provider_supported:
        return GateDecision(GateVerdict.UNRESOLVED, "provider_unsupported")
    selected = "CLAUDE.md" if "CLAUDE.md" in names else ("AGENTS.md" if "AGENTS.md" in names else None)
    if selected is None:
        return GateDecision(GateVerdict.UNRESOLVED, "no_instruction_source")
    if expected_digest is not None:
        if observed_content is None:
            return GateDecision(GateVerdict.UNRESOLVED, "instruction_digest_unverified")
        if digest_text(observed_content) != expected_digest:
            return GateDecision(GateVerdict.STALE, "instruction_digest_drift")
    return GateDecision(GateVerdict.ALLOW, selected)


def evaluate_model_lifecycle(
    *,
    requested_model: str,
    resolved_model: str,
    deprecation_at: datetime | None,
    observed_at: datetime | None = None,
    substitution_approved: bool = False,
) -> GateDecision:
    now = observed_at or datetime.now(timezone.utc)
    if requested_model != resolved_model and not substitution_approved:
        return GateDecision(GateVerdict.DENY, "silent_substitution")
    if deprecation_at is not None and now >= deprecation_at:
        return GateDecision(GateVerdict.STALE, "model_deprecated_reverify")
    if requested_model != resolved_model:
        return GateDecision(GateVerdict.STALE, "approved_substitution_reverify")
    return GateDecision(GateVerdict.ALLOW, "model_current")


def evaluate_staged_artifact_authority(
    *,
    requested_action: str,
    can_stage: bool,
    can_publish: bool,
    expected_digest: str | None = None,
    observed_digest: str | None = None,
) -> GateDecision:
    if expected_digest is not None:
        if observed_digest is None:
            return GateDecision(GateVerdict.UNRESOLVED, "artifact_digest_unverified")
        if expected_digest != observed_digest:
            return GateDecision(GateVerdict.STALE, "artifact_digest_drift")
    action = requested_action.lower()
    if action == "stage":
        return GateDecision(GateVerdict.ALLOW if can_stage else GateVerdict.DENY, "stage_authority")
    if action == "publish":
        return GateDecision(GateVerdict.ALLOW if can_publish else GateVerdict.DENY, "publish_authority")
    return GateDecision(GateVerdict.UNRESOLVED, "unknown_artifact_action")


def evaluate_ci_mcp_authority(
    *,
    capability_class: str,
    principal_class: str,
    mutation_expected: bool,
    effect_receipt_present: bool,
    verified_schema_revision: str,
    observed_schema_revision: str,
) -> GateDecision:
    if not verified_schema_revision or not observed_schema_revision:
        return GateDecision(GateVerdict.UNRESOLVED, "schema_revision_unverified")
    if verified_schema_revision != observed_schema_revision:
        return GateDecision(GateVerdict.STALE, "schema_revision_drift")
    if capability_class not in {"investigate", "manage"}:
        return GateDecision(GateVerdict.UNRESOLVED, "unknown_capability_class")
    if principal_class not in {"read_only", "scoped_write"}:
        return GateDecision(GateVerdict.UNRESOLVED, "unknown_principal_class")
    if capability_class == "manage" and principal_class == "read_only":
        return GateDecision(GateVerdict.DENY, "management_denied_for_read_only_principal")
    if mutation_expected and not effect_receipt_present:
        return GateDecision(GateVerdict.DENY, "missing_effect_receipt")
    return GateDecision(GateVerdict.ALLOW, "ci_mcp_authorized")
