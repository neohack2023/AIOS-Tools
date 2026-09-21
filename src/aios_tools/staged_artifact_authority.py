from __future__ import annotations

from dataclasses import dataclass, asdict


@dataclass(frozen=True)
class StagedArtifactAuthorityDecision:
    artifact_id: str
    artifact_digest: str
    observed_digest: str
    operation: str
    principal_stage: bool
    principal_publish: bool
    ack_state: str
    decision: str
    authority_transfer: bool = False
    external_effects: tuple[str, ...] = ()

    def as_dict(self) -> dict[str, object]:
        data = asdict(self)
        data["external_effects"] = list(self.external_effects)
        return data


def decide_staged_artifact_authority(
    *,
    artifact_id: str,
    artifact_digest: str,
    observed_digest: str,
    operation: str,
    principal_stage: bool,
    principal_publish: bool,
    ack_state: str = "CLEAR",
) -> StagedArtifactAuthorityDecision:
    """Return a pure, side-effect-free authority decision for stage vs publish.

    The function intentionally does not perform any registry, network, package,
    or release operation. It only classifies whether the caller's declared
    authority is sufficient for the requested operation against the bound
    artifact digest and acknowledgement state.
    """
    if operation not in {"STAGE", "PUBLISH"}:
        raise ValueError("operation must be STAGE or PUBLISH")
    if ack_state not in {"CLEAR", "AMBIGUOUS"}:
        raise ValueError("ack_state must be CLEAR or AMBIGUOUS")
    if len(artifact_digest) != 64 or len(observed_digest) != 64:
        raise ValueError("artifact digests must be 64-character SHA-256 hex strings")

    if artifact_digest != observed_digest:
        decision = "STALE_DIGEST"
    elif ack_state == "AMBIGUOUS":
        decision = "READBACK_REQUIRED"
    elif operation == "STAGE":
        decision = "ALLOW_STAGE" if principal_stage else "DENY_PUBLISH"
    elif principal_publish:
        decision = "ALLOW_PUBLISH"
    else:
        decision = "DENY_PUBLISH"

    return StagedArtifactAuthorityDecision(
        artifact_id=artifact_id,
        artifact_digest=artifact_digest,
        observed_digest=observed_digest,
        operation=operation,
        principal_stage=principal_stage,
        principal_publish=principal_publish,
        ack_state=ack_state,
        decision=decision,
    )
