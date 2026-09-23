from __future__ import annotations

from dataclasses import asdict, dataclass
from enum import Enum

from aios_tools.canonical import canonical_sha256


RECEIPT_SCHEMA = "drive-shadow-replication-health/v1"


class ShadowHealthError(RuntimeError):
    pass


class ShadowHealth(str, Enum):
    HEALTHY = "HEALTHY"
    LAGGING = "LAGGING"
    STALLED = "STALLED"
    PARTIAL = "PARTIAL"
    UNKNOWN = "UNKNOWN"


class RecoveryState(str, Enum):
    NONE = "NONE"
    PLANNED = "PLANNED"
    RUNNING = "RUNNING"
    PARTIAL = "PARTIAL"
    COMPLETE = "COMPLETE"
    FAILED = "FAILED"


@dataclass(frozen=True)
class ShadowHealthObservation:
    source_authority_id: str
    shadow_id: str
    replication_rule_id: str
    telemetry_available: bool
    pending_objects: int
    pending_bytes: int
    oldest_pending_age_s: int
    lag_threshold_s: int
    stall_threshold_s: int
    failed_objects: int
    destinations_total: int = 1
    destinations_current: int = 1
    metadata_match: bool = True
    recovery_batch_id: str | None = None
    recovery_state: RecoveryState = RecoveryState.NONE
    root_cause_repaired: bool = False
    post_recovery_readback: bool = False


@dataclass(frozen=True)
class ShadowHealthReceipt:
    schema: str
    receipt_id: str
    shadow_id: str
    health: ShadowHealth
    reason: str
    observation_digest: str
    authority_transfer: bool = False


def classify_shadow_health(
    observation: ShadowHealthObservation,
) -> ShadowHealthReceipt:
    for value, code in (
        (observation.source_authority_id, "source_authority_id_required"),
        (observation.shadow_id, "shadow_id_required"),
        (observation.replication_rule_id, "replication_rule_id_required"),
    ):
        if not isinstance(value, str) or not value.strip():
            raise ShadowHealthError(code)

    numeric = (
        observation.pending_objects,
        observation.pending_bytes,
        observation.oldest_pending_age_s,
        observation.lag_threshold_s,
        observation.stall_threshold_s,
        observation.failed_objects,
        observation.destinations_total,
        observation.destinations_current,
    )
    if any(value < 0 for value in numeric):
        raise ShadowHealthError("negative_health_metric")
    if observation.destinations_total < 1:
        raise ShadowHealthError("destinations_total_invalid")
    if observation.destinations_current > observation.destinations_total:
        raise ShadowHealthError("destinations_current_invalid")
    if observation.stall_threshold_s < observation.lag_threshold_s:
        raise ShadowHealthError("health_threshold_order_invalid")

    if not observation.telemetry_available:
        health = ShadowHealth.UNKNOWN
        reason = "telemetry_unavailable"
    elif observation.destinations_current < observation.destinations_total:
        health = ShadowHealth.PARTIAL
        reason = "destination_projection_partial"
    elif observation.failed_objects > 0:
        health = ShadowHealth.PARTIAL
        reason = "failed_objects_remain"
    elif not observation.metadata_match:
        health = ShadowHealth.PARTIAL
        reason = "metadata_or_fingerprint_mismatch"
    elif (
        observation.recovery_state != RecoveryState.NONE
        and observation.recovery_state != RecoveryState.COMPLETE
    ):
        health = ShadowHealth.PARTIAL
        reason = "recovery_not_complete"
    elif observation.recovery_state == RecoveryState.COMPLETE and (
        not observation.root_cause_repaired
        or not observation.post_recovery_readback
    ):
        health = ShadowHealth.PARTIAL
        reason = "recovery_readback_incomplete"
    elif (
        observation.pending_objects > 0
        and observation.oldest_pending_age_s >= observation.stall_threshold_s
    ):
        health = ShadowHealth.STALLED
        reason = "oldest_pending_exceeds_stall_threshold"
    elif (
        observation.pending_objects > 0
        or observation.oldest_pending_age_s >= observation.lag_threshold_s
    ):
        health = ShadowHealth.LAGGING
        reason = "replication_backlog_or_lag"
    else:
        health = ShadowHealth.HEALTHY
        reason = "shadow_current"

    payload = {
        **asdict(observation),
        "recovery_state": observation.recovery_state.value,
    }
    digest = canonical_sha256(payload)
    unsigned = {
        "schema": RECEIPT_SCHEMA,
        "shadow_id": observation.shadow_id,
        "health": health.value,
        "reason": reason,
        "observation_digest": digest,
        "authority_transfer": False,
    }
    return ShadowHealthReceipt(
        schema=RECEIPT_SCHEMA,
        receipt_id="dsh_" + canonical_sha256(unsigned),
        shadow_id=observation.shadow_id,
        health=health,
        reason=reason,
        observation_digest=digest,
        authority_transfer=False,
    )
