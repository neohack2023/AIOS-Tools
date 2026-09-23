import pytest

from aios_tools.experimental.mcp_interactive_parity import (
    ClaimStrength,
    DualEvidenceObservation,
    ParityState,
    compare_interactive_evidence,
)


def obs(**kwargs):
    values = dict(
        tool_call_id="call-1",
        source_system="opensearch",
        text_scope="svc",
        visual_scope="svc",
        text_window="t1",
        visual_window="t1",
        text_revision="r1",
        visual_revision="r1",
        text_fingerprint="tfp",
        visual_fingerprint="vfp",
    )
    values.update(kwargs)
    return DualEvidenceObservation(**values)


@pytest.mark.parametrize(
    ("candidate", "state", "reason"),
    [
        (obs(), ParityState.PASS, "parity"),
        (
            obs(
                text_claim_strength=ClaimStrength.CAUSAL,
                visual_support_strength=ClaimStrength.CORRELATION,
            ),
            ParityState.FAIL,
            "summary_exceeds_visual_evidence",
        ),
        (
            obs(visual_window="t0"),
            ParityState.FAIL,
            "evidence_window_mismatch",
        ),
        (
            obs(text_window="t0"),
            ParityState.FAIL,
            "evidence_window_mismatch",
        ),
        (
            obs(visual_scope="svc-b"),
            ParityState.FAIL,
            "evidence_scope_mismatch",
        ),
        (
            obs(
                visual_available=False,
                visual_scope=None,
                visual_window=None,
                visual_revision=None,
                visual_fingerprint=None,
            ),
            ParityState.DEGRADED,
            "human_verification_unavailable",
        ),
        (
            obs(visual_extra_detail=True),
            ParityState.PASS,
            "parity",
        ),
    ],
)
def test_sealed_parity_matrix(candidate, state, reason):
    receipt = compare_interactive_evidence(candidate)
    assert receipt.state == state
    assert receipt.reason == reason
    assert receipt.authority_transfer is False


def test_missing_visual_identity_fails():
    receipt = compare_interactive_evidence(obs(visual_fingerprint=None))
    assert receipt.state == ParityState.FAIL
    assert receipt.reason == "visual_identity_incomplete"


def test_receipt_is_deterministic():
    candidate = obs()
    assert compare_interactive_evidence(candidate) == compare_interactive_evidence(candidate)
