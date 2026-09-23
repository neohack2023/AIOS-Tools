from __future__ import annotations

from dataclasses import asdict, dataclass
from enum import Enum

from aios_tools.canonical import canonical_sha256


RECEIPT_SCHEMA = "agent-skill-install-lifecycle/v1"


class SkillOperation(str, Enum):
    DISCOVER = "DISCOVER"
    INSTALL = "INSTALL"
    UPDATE = "UPDATE"
    REMOVE = "REMOVE"


class SkillDecision(str, Enum):
    DISCOVER_ONLY = "DISCOVER_ONLY"
    INSTALL = "INSTALL"
    UPDATE = "UPDATE"
    NOOP = "NOOP"
    REMOVE = "REMOVE"
    BLOCK_DRIFT = "BLOCK_DRIFT"
    UNVERIFIED = "UNVERIFIED"


@dataclass(frozen=True)
class SkillLifecycleObservation:
    skill_name: str
    source_id: str
    source_revision: str | None
    candidate_digest: str | None
    target_agent: str
    operation: SkillOperation
    installed_source_id: str | None = None
    installed_revision: str | None = None
    installed_digest: str | None = None
    version_resolved: bool = True


@dataclass(frozen=True)
class SkillLifecycleReceipt:
    schema: str
    receipt_id: str
    skill_name: str
    target_agent: str
    decision: SkillDecision
    reason: str
    verification_invalidated: bool
    historical_provenance_preserved: bool
    trusted_state_granted: bool
    observation_digest: str
    authority_transfer: bool = False


def evaluate_skill_lifecycle(
    observation: SkillLifecycleObservation,
) -> SkillLifecycleReceipt:
    for value, code in (
        (observation.skill_name, "skill_name_required"),
        (observation.source_id, "source_id_required"),
        (observation.target_agent, "target_agent_required"),
    ):
        if not isinstance(value, str) or not value.strip():
            raise ValueError(code)

    verification_invalidated = False
    historical_provenance_preserved = True

    if observation.operation == SkillOperation.DISCOVER:
        decision = SkillDecision.DISCOVER_ONLY
        reason = "discovery_does_not_install_or_trust"
    elif not observation.version_resolved:
        decision = SkillDecision.UNVERIFIED
        reason = "version_or_revision_unresolved"
    elif not observation.source_revision or not observation.candidate_digest:
        decision = SkillDecision.UNVERIFIED
        reason = "candidate_identity_incomplete"
    elif (
        observation.installed_source_id is not None
        and observation.installed_source_id != observation.source_id
    ):
        decision = SkillDecision.BLOCK_DRIFT
        reason = "source_identity_drift"
    elif observation.operation == SkillOperation.INSTALL:
        decision = SkillDecision.INSTALL
        reason = "pinned_candidate_ready_for_target_install"
    elif observation.operation == SkillOperation.UPDATE:
        if observation.installed_digest == observation.candidate_digest:
            decision = SkillDecision.NOOP
            reason = "identical_content_identity"
        else:
            decision = SkillDecision.UPDATE
            reason = "content_identity_changed"
            verification_invalidated = True
    elif observation.operation == SkillOperation.REMOVE:
        decision = SkillDecision.REMOVE
        reason = "remove_availability_preserve_history"
    else:
        raise ValueError("unsupported_skill_operation")

    payload = {
        **asdict(observation),
        "operation": observation.operation.value,
    }
    digest = canonical_sha256(payload)
    unsigned = {
        "schema": RECEIPT_SCHEMA,
        "skill_name": observation.skill_name,
        "target_agent": observation.target_agent,
        "decision": decision.value,
        "reason": reason,
        "verification_invalidated": verification_invalidated,
        "historical_provenance_preserved": historical_provenance_preserved,
        "trusted_state_granted": False,
        "observation_digest": digest,
        "authority_transfer": False,
    }
    return SkillLifecycleReceipt(
        schema=RECEIPT_SCHEMA,
        receipt_id="asl_" + canonical_sha256(unsigned),
        skill_name=observation.skill_name,
        target_agent=observation.target_agent,
        decision=decision,
        reason=reason,
        verification_invalidated=verification_invalidated,
        historical_provenance_preserved=historical_provenance_preserved,
        trusted_state_granted=False,
        observation_digest=digest,
        authority_transfer=False,
    )
