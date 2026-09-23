from __future__ import annotations

from dataclasses import asdict, dataclass
from enum import Enum

from aios_tools.canonical import canonical_sha256


RECEIPT_SCHEMA = "resource-fallback-equivalence/v1"


class FallbackDecision(str, Enum):
    SELECT = "SELECT"
    STALE_LIST = "STALE_LIST"
    QUEUE_EXPIRED = "QUEUE_EXPIRED"
    NO_COMPATIBLE_CAPACITY = "NO_COMPATIBLE_CAPACITY"


@dataclass(frozen=True)
class ResourceCandidate:
    resource_id: str
    compatibility_receipt_id: str | None
    capacity_available: bool
    instance_count: int
    environment_fingerprint: str
    cost_class: str
    performance_equivalence_class: str


@dataclass(frozen=True)
class FallbackObservation:
    preference_list_digest: str
    validated_preference_list_digest: str
    candidates: tuple[ResourceCandidate, ...]
    queue_deadline_open: bool = True


@dataclass(frozen=True)
class FallbackReceipt:
    schema: str
    receipt_id: str
    decision: FallbackDecision
    reason: str
    selected_resource_id: str | None
    selection_rank: int | None
    selected_instance_count: int | None
    selected_environment_fingerprint: str | None
    observation_digest: str
    authority_transfer: bool = False


def select_prequalified_resource(
    observation: FallbackObservation,
) -> FallbackReceipt:
    if not observation.preference_list_digest.strip():
        raise ValueError("preference_list_digest_required")
    if not observation.validated_preference_list_digest.strip():
        raise ValueError("validated_preference_list_digest_required")
    if not observation.candidates:
        raise ValueError("candidate_list_required")
    if any(candidate.instance_count < 1 for candidate in observation.candidates):
        raise ValueError("instance_count_invalid")
    if len({candidate.resource_id for candidate in observation.candidates}) != len(
        observation.candidates
    ):
        raise ValueError("duplicate_resource_id")

    selected: ResourceCandidate | None = None
    selected_rank: int | None = None

    if (
        observation.preference_list_digest
        != observation.validated_preference_list_digest
    ):
        decision = FallbackDecision.STALE_LIST
        reason = "preference_list_changed_after_validation"
    elif not observation.queue_deadline_open:
        decision = FallbackDecision.QUEUE_EXPIRED
        reason = "queue_deadline_expired"
    else:
        for rank, candidate in enumerate(observation.candidates, start=1):
            if not candidate.compatibility_receipt_id:
                continue
            if candidate.capacity_available:
                selected = candidate
                selected_rank = rank
                break

        if selected is None:
            decision = FallbackDecision.NO_COMPATIBLE_CAPACITY
            reason = "no_prequalified_candidate_with_capacity"
        else:
            decision = FallbackDecision.SELECT
            reason = "first_prequalified_candidate_with_capacity"

    payload = {
        "preference_list_digest": observation.preference_list_digest,
        "validated_preference_list_digest": (
            observation.validated_preference_list_digest
        ),
        "candidates": [asdict(candidate) for candidate in observation.candidates],
        "queue_deadline_open": observation.queue_deadline_open,
    }
    digest = canonical_sha256(payload)
    unsigned = {
        "schema": RECEIPT_SCHEMA,
        "decision": decision.value,
        "reason": reason,
        "selected_resource_id": selected.resource_id if selected else None,
        "selection_rank": selected_rank,
        "selected_instance_count": selected.instance_count if selected else None,
        "selected_environment_fingerprint": (
            selected.environment_fingerprint if selected else None
        ),
        "observation_digest": digest,
        "authority_transfer": False,
    }
    return FallbackReceipt(
        schema=RECEIPT_SCHEMA,
        receipt_id="rfe_" + canonical_sha256(unsigned),
        decision=decision,
        reason=reason,
        selected_resource_id=selected.resource_id if selected else None,
        selection_rank=selected_rank,
        selected_instance_count=selected.instance_count if selected else None,
        selected_environment_fingerprint=(
            selected.environment_fingerprint if selected else None
        ),
        observation_digest=digest,
        authority_transfer=False,
    )
