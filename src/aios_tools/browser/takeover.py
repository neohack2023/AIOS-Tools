from __future__ import annotations

import asyncio
from dataclasses import dataclass
from datetime import datetime, timezone
from enum import StrEnum
import inspect
import re
from typing import Awaitable, Callable, Iterable

from .origin import NormalizedOrigin, OriginValidationError
from .redaction import SecretEvidenceBlackout


_IDENTITY_FINGERPRINT_RE = re.compile(r"^sha256:[0-9a-f]{64}$")


class TakeoverState(StrEnum):
    AUTH_REQUIRED = "AUTH_REQUIRED"
    TAKEOVER_PENDING = "TAKEOVER_PENDING"
    USER_CONTROL = "USER_CONTROL"
    VERIFY_PENDING = "VERIFY_PENDING"
    SESSION_AVAILABLE = "SESSION_AVAILABLE"
    AUTH_FAILED = "AUTH_FAILED"
    CANCELLED = "CANCELLED"
    EXPIRED = "EXPIRED"


class TakeoverBoundaryError(RuntimeError):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code


class TakeoverUserCancelled(RuntimeError):
    pass


@dataclass(frozen=True, slots=True)
class TakeoverResumeProof:
    origin: str
    identity_context_fingerprint: str
    verified_at: datetime
    verification_method: str
    authenticated: bool

    def __post_init__(self) -> None:
        normalized = NormalizedOrigin.parse(self.origin).serialize()
        if normalized != self.origin:
            raise ValueError("takeover proof origin must be exact normalized origin")
        if not _IDENTITY_FINGERPRINT_RE.fullmatch(self.identity_context_fingerprint):
            raise ValueError("takeover proof identity must be a sha256 fingerprint")
        if self.verified_at.tzinfo is None or self.verified_at.utcoffset() is None:
            raise ValueError("takeover proof timestamp must be timezone-aware")
        if not self.verification_method or any(ch.isspace() for ch in self.verification_method):
            raise ValueError("verification method must be a compact nonsecret identifier")

    def public_receipt(self) -> dict[str, object]:
        return {
            "origin": self.origin,
            "verified_at": self.verified_at.astimezone(timezone.utc).isoformat(),
            "verification_method": self.verification_method,
            "authenticated": self.authenticated,
            "identity_context_exposed": False,
        }


class TakeoverOriginGate:
    """Exact transition gate. Observing a new origin never adds it to the allowlist."""

    def __init__(self, base_origin: str, *, explicit_transition_origins: Iterable[str] = ()) -> None:
        self._base = NormalizedOrigin.parse(base_origin)
        transitions = {NormalizedOrigin.parse(value) for value in explicit_transition_origins}
        self._allowed = frozenset({self._base, *transitions})

    @property
    def base_origin(self) -> str:
        return self._base.serialize()

    @property
    def admitted_origins(self) -> tuple[str, ...]:
        return tuple(sorted(origin.serialize() for origin in self._allowed))

    def observe(self, raw_url: str) -> str:
        try:
            origin = NormalizedOrigin.parse(raw_url)
        except OriginValidationError as exc:
            raise TakeoverBoundaryError("TAKEOVER_ORIGIN_BLOCKED", "takeover navigation origin is invalid") from exc
        if origin not in self._allowed:
            raise TakeoverBoundaryError("TAKEOVER_ORIGIN_BLOCKED", "takeover navigation origin is not admitted")
        return origin.serialize()


@dataclass(frozen=True, slots=True)
class TakeoverOutcome:
    state: TakeoverState
    transitions: tuple[TakeoverState, ...]
    redactions: dict[str, object]
    proof: TakeoverResumeProof | None
    error_code: str | None
    authority_transfer: bool = False

    def public_receipt(self) -> dict[str, object]:
        return {
            "state": self.state.value,
            "transitions": [state.value for state in self.transitions],
            "redactions": dict(self.redactions),
            "proof": None if self.proof is None else self.proof.public_receipt(),
            "error_code": self.error_code,
            "authority_transfer": False,
        }


async def _maybe_await(callback: Callable[[], object] | None) -> None:
    if callback is None:
        return
    result = callback()
    if inspect.isawaitable(result):
        await result


class UserTakeoverCheckpoint:
    def __init__(
        self,
        *,
        target_origin: str,
        timeout_seconds: float,
        explicit_transition_origins: Iterable[str] = (),
    ) -> None:
        if timeout_seconds <= 0:
            raise ValueError("takeover timeout must be positive")
        self.timeout_seconds = float(timeout_seconds)
        self.origin_gate = TakeoverOriginGate(
            target_origin,
            explicit_transition_origins=explicit_transition_origins,
        )

    async def run(
        self,
        *,
        user_control: Callable[[SecretEvidenceBlackout, TakeoverOriginGate], Awaitable[None]],
        verifier: Callable[[], Awaitable[TakeoverResumeProof | None]],
        purge_partial: Callable[[], object] | None = None,
    ) -> TakeoverOutcome:
        transitions = [TakeoverState.AUTH_REQUIRED, TakeoverState.TAKEOVER_PENDING]
        blackout = SecretEvidenceBlackout()
        proof: TakeoverResumeProof | None = None
        try:
            async with asyncio.timeout(self.timeout_seconds):
                transitions.append(TakeoverState.USER_CONTROL)
                with blackout:
                    await user_control(blackout, self.origin_gate)
                transitions.append(TakeoverState.VERIFY_PENDING)
                proof = await verifier()
                if proof is None or not proof.authenticated:
                    await _maybe_await(purge_partial)
                    transitions.append(TakeoverState.AUTH_FAILED)
                    return TakeoverOutcome(
                        state=TakeoverState.AUTH_FAILED,
                        transitions=tuple(transitions),
                        redactions=blackout.public_receipt(),
                        proof=None,
                        error_code="POST_TAKEOVER_VERIFICATION_FAILED",
                    )
                if proof.origin != self.origin_gate.base_origin:
                    await _maybe_await(purge_partial)
                    transitions.append(TakeoverState.AUTH_FAILED)
                    return TakeoverOutcome(
                        state=TakeoverState.AUTH_FAILED,
                        transitions=tuple(transitions),
                        redactions=blackout.public_receipt(),
                        proof=None,
                        error_code="POST_TAKEOVER_ORIGIN_MISMATCH",
                    )
                transitions.append(TakeoverState.SESSION_AVAILABLE)
                return TakeoverOutcome(
                    state=TakeoverState.SESSION_AVAILABLE,
                    transitions=tuple(transitions),
                    redactions=blackout.public_receipt(),
                    proof=proof,
                    error_code=None,
                )
        except TakeoverUserCancelled:
            await _maybe_await(purge_partial)
            transitions.append(TakeoverState.CANCELLED)
            return TakeoverOutcome(
                state=TakeoverState.CANCELLED,
                transitions=tuple(transitions),
                redactions=blackout.public_receipt(),
                proof=None,
                error_code="TAKEOVER_CANCELLED",
            )
        except TakeoverBoundaryError as exc:
            await _maybe_await(purge_partial)
            transitions.append(TakeoverState.AUTH_FAILED)
            return TakeoverOutcome(
                state=TakeoverState.AUTH_FAILED,
                transitions=tuple(transitions),
                redactions=blackout.public_receipt(),
                proof=None,
                error_code=exc.code,
            )
        except TimeoutError:
            await _maybe_await(purge_partial)
            transitions.append(TakeoverState.EXPIRED)
            return TakeoverOutcome(
                state=TakeoverState.EXPIRED,
                transitions=tuple(transitions),
                redactions=blackout.public_receipt(),
                proof=None,
                error_code="TAKEOVER_TIMEOUT",
            )
        except asyncio.CancelledError:
            await _maybe_await(purge_partial)
            raise


class ReauthReason(StrEnum):
    SESSION_EXPIRED = "SESSION_EXPIRED"
    ORIGIN_MISMATCH = "ORIGIN_MISMATCH"
    IDENTITY_MISMATCH = "IDENTITY_MISMATCH"
    PRIVILEGE_CHANGE = "PRIVILEGE_CHANGE"
    RISK_EVENT = "RISK_EVENT"
    SERVER_LOGOUT = "SERVER_LOGOUT"
    BACKEND_UNAVAILABLE = "BACKEND_UNAVAILABLE"
    SITE_REQUIRED = "SITE_REQUIRED"


@dataclass(frozen=True, slots=True)
class ReauthDecision:
    required: bool
    reason: ReauthReason
    reseal_allowed: bool

    @classmethod
    def for_reason(cls, reason: ReauthReason, *, fresh_verified_proof: bool = False) -> "ReauthDecision":
        high_risk = {ReauthReason.PRIVILEGE_CHANGE, ReauthReason.RISK_EVENT}
        reseal_allowed = bool(fresh_verified_proof) and reason not in high_risk
        return cls(required=True, reason=reason, reseal_allowed=reseal_allowed)
