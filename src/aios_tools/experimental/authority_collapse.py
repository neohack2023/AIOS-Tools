from __future__ import annotations

from dataclasses import asdict, dataclass
from enum import Enum

from aios_tools.canonical import canonical_sha256


RECEIPT_SCHEMA = "authority-collapse-decision/v1"


class AuthorityCollapseError(RuntimeError):
    pass


class AuthorityClass(str, Enum):
    AUTHORITATIVE_CURRENT = "AUTHORITATIVE_CURRENT"
    AUTHORITATIVE_SUPERSEDED = "AUTHORITATIVE_SUPERSEDED"
    RESEARCH_ONLY = "RESEARCH_ONLY"
    CONVERSATION_EVIDENCE = "CONVERSATION_EVIDENCE"
    SHADOW_NONAUTHORITY = "SHADOW_NONAUTHORITY"
    AUTHORITY_CONFLICT = "AUTHORITY_CONFLICT"


class ClaimUse(str, Enum):
    CURRENT_STATE = "CURRENT_STATE"
    HISTORICAL_ONLY = "HISTORICAL_ONLY"
    EVIDENCE_ONLY = "EVIDENCE_ONLY"
    TASK_ONLY = "TASK_ONLY"
    ROUTING_ONLY = "ROUTING_ONLY"
    BLOCK = "BLOCK"


class GateType(str, Enum):
    ADVISORY = "ADVISORY"
    WORKFLOW_APPROVAL = "WORKFLOW_APPROVAL"
    SECURITY_SCAN = "SECURITY_SCAN"


class GateDecision(str, Enum):
    EVIDENCE_ONLY = "EVIDENCE_ONLY"
    GATE_PASS = "GATE_PASS"
    STALE = "STALE"
    BYPASS = "BYPASS"
    BLOCK = "BLOCK"


@dataclass(frozen=True)
class ClaimObservation:
    source_id: str
    source_revision: str
    authority_owner: str
    authority_domain: str
    requested_domain: str
    authority_class: AuthorityClass
    supersession_link: str | None = None


@dataclass(frozen=True)
class GateObservation:
    gate_id: str
    gate_type: GateType
    bound_revision: str
    current_revision: str
    policy_id: str
    policy_revision: str
    current_policy_revision: str
    result_pass: bool
    capability_enabled: bool = True
    producer_identity: str | None = None
    reviewer_identity: str | None = None
    approval_scope_matches: bool = True
    bypass_used: bool = False
    bypass_actor: str | None = None
    bypass_authority_source: str | None = None
    scan_complete: bool = True


@dataclass(frozen=True)
class AuthorityDecisionReceipt:
    schema: str
    receipt_id: str
    decision_kind: str
    decision: str
    reason: str
    observation_digest: str
    authority_transfer: bool = False


def _require(value: str, code: str) -> None:
    if not isinstance(value, str) or not value.strip():
        raise AuthorityCollapseError(code)


def evaluate_claim(observation: ClaimObservation) -> AuthorityDecisionReceipt:
    _require(observation.source_id, "source_id_required")
    _require(observation.source_revision, "source_revision_required")
    _require(observation.authority_owner, "authority_owner_required")
    _require(observation.authority_domain, "authority_domain_required")
    _require(observation.requested_domain, "requested_domain_required")

    if observation.authority_class == AuthorityClass.AUTHORITY_CONFLICT:
        decision = ClaimUse.BLOCK
        reason = "authority_conflict"
    elif observation.authority_class == AuthorityClass.AUTHORITATIVE_CURRENT:
        if observation.authority_domain != observation.requested_domain:
            decision = ClaimUse.BLOCK
            reason = "authority_domain_mismatch"
        else:
            decision = ClaimUse.CURRENT_STATE
            reason = "current_authority_matches_domain"
    elif observation.authority_class == AuthorityClass.AUTHORITATIVE_SUPERSEDED:
        if not observation.supersession_link:
            decision = ClaimUse.BLOCK
            reason = "supersession_link_required"
        else:
            decision = ClaimUse.HISTORICAL_ONLY
            reason = "superseded_authority"
    elif observation.authority_class == AuthorityClass.RESEARCH_ONLY:
        decision = ClaimUse.EVIDENCE_ONLY
        reason = "research_not_authority"
    elif observation.authority_class == AuthorityClass.CONVERSATION_EVIDENCE:
        decision = ClaimUse.TASK_ONLY
        reason = "conversation_not_durable_authority"
    elif observation.authority_class == AuthorityClass.SHADOW_NONAUTHORITY:
        decision = ClaimUse.ROUTING_ONLY
        reason = "shadow_nonauthority"
    else:
        raise AuthorityCollapseError("unsupported_authority_class")

    return _receipt("claim", observation, decision.value, reason)


def evaluate_gate(observation: GateObservation) -> AuthorityDecisionReceipt:
    for value, code in (
        (observation.gate_id, "gate_id_required"),
        (observation.bound_revision, "bound_revision_required"),
        (observation.current_revision, "current_revision_required"),
        (observation.policy_id, "policy_id_required"),
        (observation.policy_revision, "policy_revision_required"),
        (observation.current_policy_revision, "current_policy_revision_required"),
    ):
        _require(value, code)

    if observation.gate_type == GateType.ADVISORY:
        decision = GateDecision.EVIDENCE_ONLY
        reason = "advisory_has_no_terminal_effect"
    elif observation.bound_revision != observation.current_revision:
        decision = GateDecision.STALE
        reason = "artifact_revision_changed"
    elif observation.policy_revision != observation.current_policy_revision:
        decision = GateDecision.STALE
        reason = "policy_revision_changed"
    elif observation.bypass_used:
        if not observation.bypass_actor or not observation.bypass_authority_source:
            decision = GateDecision.BLOCK
            reason = "bypass_provenance_required"
        else:
            decision = GateDecision.BYPASS
            reason = "authorized_bypass_preserved"
    elif observation.gate_type == GateType.WORKFLOW_APPROVAL:
        if not observation.capability_enabled:
            decision = GateDecision.EVIDENCE_ONLY
            reason = "approval_capability_not_enabled"
        elif (
            observation.producer_identity
            and observation.reviewer_identity
            and observation.producer_identity == observation.reviewer_identity
        ):
            decision = GateDecision.BLOCK
            reason = "reviewer_independence_failed"
        elif not observation.approval_scope_matches:
            decision = GateDecision.BLOCK
            reason = "approval_scope_mismatch"
        elif not observation.result_pass:
            decision = GateDecision.BLOCK
            reason = "approval_gate_failed"
        else:
            decision = GateDecision.GATE_PASS
            reason = "workflow_approval_passed"
    elif observation.gate_type == GateType.SECURITY_SCAN:
        if not observation.scan_complete:
            decision = GateDecision.BLOCK
            reason = "security_scan_incomplete"
        elif not observation.result_pass:
            decision = GateDecision.BLOCK
            reason = "security_scan_failed"
        else:
            decision = GateDecision.GATE_PASS
            reason = "security_scan_passed"
    else:
        raise AuthorityCollapseError("unsupported_gate_type")

    return _receipt("gate", observation, decision.value, reason)


def _receipt(
    decision_kind: str,
    observation: ClaimObservation | GateObservation,
    decision: str,
    reason: str,
) -> AuthorityDecisionReceipt:
    payload = asdict(observation)
    for key, value in list(payload.items()):
        if isinstance(value, Enum):
            payload[key] = value.value
    observation_digest = canonical_sha256(payload)
    unsigned = {
        "schema": RECEIPT_SCHEMA,
        "decision_kind": decision_kind,
        "decision": decision,
        "reason": reason,
        "observation_digest": observation_digest,
        "authority_transfer": False,
    }
    return AuthorityDecisionReceipt(
        schema=RECEIPT_SCHEMA,
        receipt_id="acr_" + canonical_sha256(unsigned),
        decision_kind=decision_kind,
        decision=decision,
        reason=reason,
        observation_digest=observation_digest,
        authority_transfer=False,
    )
