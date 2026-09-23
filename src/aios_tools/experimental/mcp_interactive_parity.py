from __future__ import annotations

from dataclasses import asdict, dataclass
from enum import Enum

from aios_tools.canonical import canonical_sha256


RECEIPT_SCHEMA = "mcp-interactive-parity/v1"


class ParityState(str, Enum):
    PASS = "PASS"
    FAIL = "FAIL"
    DEGRADED = "DEGRADED"


class ClaimStrength(str, Enum):
    CORRELATION = "CORRELATION"
    CAUSAL = "CAUSAL"


@dataclass(frozen=True)
class DualEvidenceObservation:
    tool_call_id: str
    source_system: str
    text_scope: str
    visual_scope: str | None
    text_window: str
    visual_window: str | None
    text_revision: str
    visual_revision: str | None
    text_fingerprint: str
    visual_fingerprint: str | None
    text_claim_strength: ClaimStrength = ClaimStrength.CORRELATION
    visual_support_strength: ClaimStrength = ClaimStrength.CORRELATION
    visual_available: bool = True
    visual_extra_detail: bool = False


@dataclass(frozen=True)
class ParityReceipt:
    schema: str
    receipt_id: str
    tool_call_id: str
    state: ParityState
    reason: str
    observation_digest: str
    authority_transfer: bool = False


def compare_interactive_evidence(
    observation: DualEvidenceObservation,
) -> ParityReceipt:
    for value, code in (
        (observation.tool_call_id, "tool_call_id_required"),
        (observation.source_system, "source_system_required"),
        (observation.text_scope, "text_scope_required"),
        (observation.text_window, "text_window_required"),
        (observation.text_revision, "text_revision_required"),
        (observation.text_fingerprint, "text_fingerprint_required"),
    ):
        if not isinstance(value, str) or not value.strip():
            raise ValueError(code)

    if not observation.visual_available:
        state = ParityState.DEGRADED
        reason = "human_verification_unavailable"
    elif not all(
        (
            observation.visual_scope,
            observation.visual_window,
            observation.visual_revision,
            observation.visual_fingerprint,
        )
    ):
        state = ParityState.FAIL
        reason = "visual_identity_incomplete"
    elif observation.text_scope != observation.visual_scope:
        state = ParityState.FAIL
        reason = "evidence_scope_mismatch"
    elif observation.text_window != observation.visual_window:
        state = ParityState.FAIL
        reason = "evidence_window_mismatch"
    elif observation.text_revision != observation.visual_revision:
        state = ParityState.FAIL
        reason = "evidence_revision_mismatch"
    elif (
        observation.text_claim_strength == ClaimStrength.CAUSAL
        and observation.visual_support_strength != ClaimStrength.CAUSAL
    ):
        state = ParityState.FAIL
        reason = "summary_exceeds_visual_evidence"
    else:
        state = ParityState.PASS
        reason = "parity"

    payload = {
        **asdict(observation),
        "text_claim_strength": observation.text_claim_strength.value,
        "visual_support_strength": observation.visual_support_strength.value,
    }
    digest = canonical_sha256(payload)
    unsigned = {
        "schema": RECEIPT_SCHEMA,
        "tool_call_id": observation.tool_call_id,
        "state": state.value,
        "reason": reason,
        "observation_digest": digest,
        "authority_transfer": False,
    }
    return ParityReceipt(
        schema=RECEIPT_SCHEMA,
        receipt_id="mip_" + canonical_sha256(unsigned),
        tool_call_id=observation.tool_call_id,
        state=state,
        reason=reason,
        observation_digest=digest,
        authority_transfer=False,
    )
