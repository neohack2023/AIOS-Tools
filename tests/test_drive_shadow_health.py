import pytest

from aios_tools.experimental.drive_shadow_health import (
    RecoveryState,
    ShadowHealth,
    ShadowHealthError,
    ShadowHealthObservation,
    classify_shadow_health,
)


def obs(**kwargs):
    values = dict(
        source_authority_id="notion-authority",
        shadow_id="drive-shadow",
        replication_rule_id="rule-1",
        telemetry_available=True,
        pending_objects=0,
        pending_bytes=0,
        oldest_pending_age_s=0,
        lag_threshold_s=60,
        stall_threshold_s=300,
        failed_objects=0,
    )
    values.update(kwargs)
    return ShadowHealthObservation(**values)


@pytest.mark.parametrize(
    ("candidate", "expected"),
    [
        (obs(), ShadowHealth.HEALTHY),
        (
            obs(pending_objects=3, oldest_pending_age_s=120),
            ShadowHealth.LAGGING,
        ),
        (
            obs(pending_objects=3, oldest_pending_age_s=600),
            ShadowHealth.STALLED,
        ),
        (
            obs(destinations_total=2, destinations_current=1),
            ShadowHealth.PARTIAL,
        ),
        (obs(metadata_match=False), ShadowHealth.PARTIAL),
        (obs(failed_objects=1), ShadowHealth.PARTIAL),
        (obs(telemetry_available=False), ShadowHealth.UNKNOWN),
        (
            obs(
                recovery_batch_id="batch-1",
                recovery_state=RecoveryState.COMPLETE,
                root_cause_repaired=True,
                post_recovery_readback=False,
            ),
            ShadowHealth.PARTIAL,
        ),
        (
            obs(
                recovery_batch_id="batch-1",
                recovery_state=RecoveryState.COMPLETE,
                root_cause_repaired=True,
                post_recovery_readback=True,
            ),
            ShadowHealth.HEALTHY,
        ),
    ],
)
def test_shadow_health_matrix(candidate, expected):
    receipt = classify_shadow_health(candidate)
    assert receipt.health == expected
    assert receipt.authority_transfer is False


def test_incomplete_recovery_never_reports_healthy():
    receipt = classify_shadow_health(
        obs(
            recovery_batch_id="batch-1",
            recovery_state=RecoveryState.RUNNING,
            root_cause_repaired=True,
        )
    )
    assert receipt.health == ShadowHealth.PARTIAL


def test_invalid_thresholds_fail_closed():
    with pytest.raises(
        ShadowHealthError,
        match="health_threshold_order_invalid",
    ):
        classify_shadow_health(
            obs(lag_threshold_s=300, stall_threshold_s=60)
        )


def test_receipt_is_deterministic():
    candidate = obs()
    assert classify_shadow_health(candidate) == classify_shadow_health(candidate)
