from __future__ import annotations

import asyncio
from datetime import datetime, timezone

import pytest

from aios_tools.browser.redaction import SecretEvidenceKind
from aios_tools.browser.session import identity_fingerprint
from aios_tools.browser.takeover import (
    ReauthDecision,
    ReauthReason,
    TakeoverResumeProof,
    TakeoverState,
    TakeoverUserCancelled,
    UserTakeoverCheckpoint,
)


ORIGIN = "https://app.example.invalid"
SSO_ORIGIN = "https://login.example.invalid"
IDENTITY_FP = identity_fingerprint("synthetic-user@example.invalid")
SYNTHETIC_SECRET = "fixture-password-never-record"


def proof(*, origin: str = ORIGIN, authenticated: bool = True) -> TakeoverResumeProof:
    return TakeoverResumeProof(
        origin=origin,
        identity_context_fingerprint=IDENTITY_FP,
        verified_at=datetime(2026, 8, 23, 14, 0, tzinfo=timezone.utc),
        verification_method="synthetic-page-assertion",
        authenticated=authenticated,
    )


@pytest.mark.asyncio
async def test_takeover_success_requires_post_control_verification():
    checkpoint = UserTakeoverCheckpoint(target_origin=ORIGIN, timeout_seconds=1)

    async def user_control(blackout, origin_gate):
        assert blackout.active is True
        assert origin_gate.observe(f"{ORIGIN}/login") == ORIGIN
        blackout.redact_form_value(SYNTHETIC_SECRET)

    async def verifier():
        return proof()

    outcome = await checkpoint.run(user_control=user_control, verifier=verifier)
    assert outcome.state is TakeoverState.SESSION_AVAILABLE
    assert outcome.transitions == (
        TakeoverState.AUTH_REQUIRED,
        TakeoverState.TAKEOVER_PENDING,
        TakeoverState.USER_CONTROL,
        TakeoverState.VERIFY_PENDING,
        TakeoverState.SESSION_AVAILABLE,
    )
    rendered = repr(outcome.public_receipt())
    assert SYNTHETIC_SECRET not in rendered
    assert IDENTITY_FP not in rendered
    assert outcome.public_receipt()["authority_transfer"] is False


@pytest.mark.asyncio
async def test_post_takeover_verification_required_before_session_available():
    purged = []
    checkpoint = UserTakeoverCheckpoint(target_origin=ORIGIN, timeout_seconds=1)

    async def user_control(blackout, origin_gate):
        assert blackout.active

    async def verifier():
        return None

    outcome = await checkpoint.run(
        user_control=user_control,
        verifier=verifier,
        purge_partial=lambda: purged.append("purged"),
    )
    assert outcome.state is TakeoverState.AUTH_FAILED
    assert outcome.error_code == "POST_TAKEOVER_VERIFICATION_FAILED"
    assert purged == ["purged"]
    assert TakeoverState.SESSION_AVAILABLE not in outcome.transitions


@pytest.mark.asyncio
async def test_takeover_timeout_is_bounded_and_fail_visible():
    purged = []
    checkpoint = UserTakeoverCheckpoint(target_origin=ORIGIN, timeout_seconds=0.02)

    async def user_control(blackout, origin_gate):
        await asyncio.sleep(0.2)

    async def verifier():
        raise AssertionError("verifier must not run after timeout")

    outcome = await checkpoint.run(
        user_control=user_control,
        verifier=verifier,
        purge_partial=lambda: purged.append("purged"),
    )
    assert outcome.state is TakeoverState.EXPIRED
    assert outcome.error_code == "TAKEOVER_TIMEOUT"
    assert purged == ["purged"]


@pytest.mark.asyncio
async def test_takeover_cancel_purges_partial_state():
    purged = []
    checkpoint = UserTakeoverCheckpoint(target_origin=ORIGIN, timeout_seconds=1)

    async def user_control(blackout, origin_gate):
        blackout.redact_form_value(SYNTHETIC_SECRET)
        raise TakeoverUserCancelled()

    async def verifier():
        raise AssertionError("verifier must not run after cancellation")

    outcome = await checkpoint.run(
        user_control=user_control,
        verifier=verifier,
        purge_partial=lambda: purged.append("purged"),
    )
    assert outcome.state is TakeoverState.CANCELLED
    assert outcome.error_code == "TAKEOVER_CANCELLED"
    assert purged == ["purged"]
    assert SYNTHETIC_SECRET not in repr(outcome.public_receipt())


@pytest.mark.asyncio
async def test_external_task_cancellation_purges_partial_state_and_propagates():
    purged = []
    entered = asyncio.Event()
    checkpoint = UserTakeoverCheckpoint(target_origin=ORIGIN, timeout_seconds=5)

    async def user_control(blackout, origin_gate):
        entered.set()
        await asyncio.Event().wait()

    async def verifier():
        return proof()

    task = asyncio.create_task(
        checkpoint.run(
            user_control=user_control,
            verifier=verifier,
            purge_partial=lambda: purged.append("purged"),
        )
    )
    await entered.wait()
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task
    assert purged == ["purged"]


@pytest.mark.asyncio
async def test_sso_cross_origin_does_not_auto_widen_takeover_origins():
    purged = []
    checkpoint = UserTakeoverCheckpoint(target_origin=ORIGIN, timeout_seconds=1)
    before = checkpoint.origin_gate.admitted_origins

    async def user_control(blackout, origin_gate):
        origin_gate.observe(f"{SSO_ORIGIN}/authorize")

    async def verifier():
        return proof()

    outcome = await checkpoint.run(
        user_control=user_control,
        verifier=verifier,
        purge_partial=lambda: purged.append("purged"),
    )
    assert outcome.state is TakeoverState.AUTH_FAILED
    assert outcome.error_code == "TAKEOVER_ORIGIN_BLOCKED"
    assert checkpoint.origin_gate.admitted_origins == before
    assert SSO_ORIGIN not in checkpoint.origin_gate.admitted_origins
    assert purged == ["purged"]


@pytest.mark.asyncio
async def test_explicit_sso_origin_can_be_preadmitted_without_widening_base_origin():
    checkpoint = UserTakeoverCheckpoint(
        target_origin=ORIGIN,
        timeout_seconds=1,
        explicit_transition_origins=(SSO_ORIGIN,),
    )

    async def user_control(blackout, origin_gate):
        assert origin_gate.observe(f"{SSO_ORIGIN}/authorize") == SSO_ORIGIN
        assert origin_gate.observe(f"{ORIGIN}/callback") == ORIGIN

    async def verifier():
        return proof()

    outcome = await checkpoint.run(user_control=user_control, verifier=verifier)
    assert outcome.state is TakeoverState.SESSION_AVAILABLE
    assert checkpoint.origin_gate.base_origin == ORIGIN
    assert set(checkpoint.origin_gate.admitted_origins) == {ORIGIN, SSO_ORIGIN}


@pytest.mark.asyncio
async def test_takeover_resume_proof_origin_must_match_target_origin():
    purged = []
    checkpoint = UserTakeoverCheckpoint(
        target_origin=ORIGIN,
        timeout_seconds=1,
        explicit_transition_origins=(SSO_ORIGIN,),
    )

    async def user_control(blackout, origin_gate):
        origin_gate.observe(f"{SSO_ORIGIN}/authorize")

    async def verifier():
        return proof(origin=SSO_ORIGIN)

    outcome = await checkpoint.run(
        user_control=user_control,
        verifier=verifier,
        purge_partial=lambda: purged.append("purged"),
    )
    assert outcome.state is TakeoverState.AUTH_FAILED
    assert outcome.error_code == "POST_TAKEOVER_ORIGIN_MISMATCH"
    assert purged == ["purged"]


def test_privilege_change_requires_reauth_and_does_not_silently_reseal():
    decision = ReauthDecision.for_reason(ReauthReason.PRIVILEGE_CHANGE, fresh_verified_proof=False)
    assert decision.required is True
    assert decision.reseal_allowed is False


def test_risk_event_remains_reauth_boundary_even_with_prior_session():
    decision = ReauthDecision.for_reason(ReauthReason.RISK_EVENT, fresh_verified_proof=False)
    assert decision.required is True
    assert decision.reseal_allowed is False


def test_takeover_checkpoint_has_no_unbounded_debug_mode_switch():
    signature = set(__import__("inspect").signature(UserTakeoverCheckpoint.__init__).parameters)
    assert "pwdebug" not in signature
    assert "pause" not in signature
    assert "timeout_seconds" in signature
