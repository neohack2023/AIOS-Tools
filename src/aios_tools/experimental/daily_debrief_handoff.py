from __future__ import annotations

import re
from typing import Any

from aios_tools.canonical import canonical_sha256
from aios_tools.experimental.daily_debrief_projection import (
    DailyDebriefProjectionState,
    projection_digest,
)

HANDOFF_SCHEMA = "daily-debrief-implementation-handoff/v1"
_REPOSITORY_RE = re.compile(r"^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$")
_SCOPE_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:/-]{0,127}$")


class HandoffError(RuntimeError):
    pass


class HandoffNotReady(HandoffError):
    pass


def _ready_facts(
    state: DailyDebriefProjectionState,
    lineage_key: str,
    *,
    min_distinct_debriefs: int = 2,
    min_evidence: int = 2,
) -> dict[str, Any]:
    lineage = state.lineages.get(lineage_key)
    if lineage is None:
        raise HandoffError("handoff_lineage_not_found")

    evidence_count = len(lineage.event_ids)
    distinct_debriefs = len(
        {source_id.split("::", 1)[0] for source_id in lineage.source_ids}
    )
    if evidence_count < min_evidence:
        raise HandoffNotReady("handoff_evidence_threshold_not_met")
    if distinct_debriefs < min_distinct_debriefs:
        raise HandoffNotReady("handoff_debrief_threshold_not_met")
    if lineage.live_verified_count <= 0:
        raise HandoffNotReady("handoff_live_verification_required")
    if lineage.remaining_test_ids:
        raise HandoffNotReady("handoff_remaining_tests_unresolved")

    return {
        "evidence_count": evidence_count,
        "distinct_debriefs": distinct_debriefs,
        "source_event_ids": list(lineage.event_ids),
        "source_ids": list(lineage.source_ids),
        "implementation_consequences": list(
            lineage.implementation_consequences
        ),
        "resolved_test_ids": list(lineage.resolved_test_ids),
        "simulation_pass_count": lineage.simulation_pass_count,
        "live_verified_count": lineage.live_verified_count,
    }


def build_implementation_handoff(
    state: DailyDebriefProjectionState,
    *,
    lineage: str,
    scope_key: str,
    repository: str,
    parent_issue: int = 74,
) -> dict[str, Any]:
    if not _SCOPE_RE.fullmatch(scope_key):
        raise HandoffError("handoff_scope_invalid")
    if not _REPOSITORY_RE.fullmatch(repository):
        raise HandoffError("handoff_repository_invalid")
    if not isinstance(parent_issue, int) or parent_issue <= 0:
        raise HandoffError("handoff_parent_issue_invalid")

    envelope = {
        "schema": HANDOFF_SCHEMA,
        "scope_key": scope_key,
        "repository": repository,
        "parent_intake_issue": parent_issue,
        "lineage": lineage,
        "candidate_state": "READY_FOR_IMPLEMENTATION_PLAN",
        "projection_digest": projection_digest(state),
        **_ready_facts(state, lineage),
        "intake": {
            "target": "existing_daily_debrief_implementation_intake",
            "submission_mode": "HUMAN_GATED_DRAFT",
            "stone_mason_review_required": True,
            "one_concern_per_branch_pr": True,
            "draft_pr_default": True,
            "exact_head_ci_required": True,
            "authority_security_rollback_required": True,
        },
        "authority": {
            "read_only": True,
            "human_submission_required": True,
            "automatic_issue_creation": False,
            "automatic_pr_creation": False,
            "automatic_merge": False,
            "automatic_deployment": False,
            "automatic_runtime_activation": False,
            "automatic_canon_promotion": False,
            "automatic_trusted_memory_promotion": False,
            "authority_transfer": False,
        },
    }
    envelope["handoff_id"] = "ddh_" + canonical_sha256(envelope)
    return envelope


def validate_implementation_handoff(envelope: dict[str, Any]) -> None:
    if not isinstance(envelope, dict):
        raise HandoffError("handoff_not_object")
    if envelope.get("schema") != HANDOFF_SCHEMA:
        raise HandoffError("unsupported_handoff_schema")
    if envelope.get("candidate_state") != "READY_FOR_IMPLEMENTATION_PLAN":
        raise HandoffError("handoff_candidate_state_invalid")

    authority = envelope.get("authority")
    if not isinstance(authority, dict):
        raise HandoffError("handoff_authority_missing")
    if authority.get("read_only") is not True:
        raise HandoffError("handoff_read_only_required")
    if authority.get("human_submission_required") is not True:
        raise HandoffError("handoff_human_submission_required")

    forbidden = (
        "automatic_issue_creation",
        "automatic_pr_creation",
        "automatic_merge",
        "automatic_deployment",
        "automatic_runtime_activation",
        "automatic_canon_promotion",
        "automatic_trusted_memory_promotion",
        "authority_transfer",
    )
    if any(authority.get(key) is not False for key in forbidden):
        raise HandoffError("handoff_automatic_authority_forbidden")

    handoff_id = envelope.get("handoff_id")
    if not isinstance(handoff_id, str) or not handoff_id.startswith("ddh_"):
        raise HandoffError("handoff_id_invalid")
    unsigned = {
        key: value
        for key, value in envelope.items()
        if key != "handoff_id"
    }
    if handoff_id != "ddh_" + canonical_sha256(unsigned):
        raise HandoffError("handoff_digest_mismatch")


def render_github_issue_draft(envelope: dict[str, Any]) -> dict[str, str]:
    validate_implementation_handoff(envelope)
    consequences = "\n".join(
        f"- {item}" for item in envelope["implementation_consequences"]
    ) or "- None recorded."
    sources = "\n".join(
        f"- {item}" for item in envelope["source_ids"]
    )
    resolved = "\n".join(
        f"- {item}" for item in envelope["resolved_test_ids"]
    ) or "- None recorded."

    title = "Implement Daily Debrief lineage: " + envelope["lineage"]
    body = f"""## Purpose

Create one bounded implementation slice for {envelope["lineage"]} from a governed Daily Debrief handoff.

## Governing intake

- Parent intake: #{envelope["parent_intake_issue"]}
- Handoff ID: {envelope["handoff_id"]}
- Scope: {envelope["scope_key"]}
- Projection digest: {envelope["projection_digest"]}
- Candidate state: {envelope["candidate_state"]}

## Evidence

Evidence events: {envelope["evidence_count"]}
Distinct debriefs: {envelope["distinct_debriefs"]}
Live verification passes: {envelope["live_verified_count"]}
Simulation passes: {envelope["simulation_pass_count"]}

Source identities:
{sources}

## Implementation consequences

{consequences}

## Resolved validation gates

{resolved}

## Required execution boundary

- One coherent concern per branch/PR.
- No direct write to main.
- Draft PR by default.
- Deterministic tests required.
- Exact-head CI required before merge.
- Record authority/security impact and rollback.
- Research evidence does not self-promote authority.
- Human/governed submission remains required.

## Authority

This is a read-only draft. It does not create an issue, branch, PR, merge, deployment, runtime activation, Canon promotion, or Trusted Memory promotion.
"""
    return {"title": title, "body": body}
