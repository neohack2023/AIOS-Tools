from __future__ import annotations

from dataclasses import asdict, dataclass
from enum import Enum

from aios_tools.canonical import canonical_sha256


RECEIPT_SCHEMA = "prompt-cache-isolation/v1"


class CacheDecision(str, Enum):
    REUSE_ALLOWED = "REUSE_ALLOWED"
    MISS_REBUILD = "MISS_REBUILD"
    BLOCK_CROSS_TENANT = "BLOCK_CROSS_TENANT"
    FRESHNESS_EVIDENCE_REQUIRED = "FRESHNESS_EVIDENCE_REQUIRED"
    BYPASS_CACHE = "BYPASS_CACHE"


@dataclass(frozen=True)
class CacheObservation:
    request_tenant_hash: str
    cache_tenant_hash: str | None
    prefix_match: bool
    system_prompt_match: bool
    tool_definition_match: bool
    policy_revision_match: bool
    ttl_valid: bool
    cache_available: bool
    cache_hit: bool
    freshness_required: bool
    correctness_evidence_current: bool


@dataclass(frozen=True)
class CacheDecisionReceipt:
    schema: str
    receipt_id: str
    decision: CacheDecision
    reason: str
    observation_digest: str
    authority_transfer: bool = False


def decide_cache_use(observation: CacheObservation) -> CacheDecisionReceipt:
    if not observation.request_tenant_hash.strip():
        raise ValueError("request_tenant_hash_required")

    if not observation.cache_available:
        decision = CacheDecision.BYPASS_CACHE
        reason = "cache_unavailable"
    elif (
        observation.cache_tenant_hash is None
        or observation.cache_tenant_hash != observation.request_tenant_hash
    ):
        decision = CacheDecision.BLOCK_CROSS_TENANT
        reason = "tenant_boundary_mismatch"
    elif not all(
        (
            observation.prefix_match,
            observation.system_prompt_match,
            observation.tool_definition_match,
            observation.policy_revision_match,
            observation.ttl_valid,
        )
    ):
        decision = CacheDecision.MISS_REBUILD
        reason = "cache_identity_or_ttl_changed"
    elif (
        observation.freshness_required
        and not observation.correctness_evidence_current
    ):
        decision = CacheDecision.FRESHNESS_EVIDENCE_REQUIRED
        reason = "cache_hit_not_freshness_evidence"
    else:
        decision = CacheDecision.REUSE_ALLOWED
        reason = "cache_identity_current"

    payload = asdict(observation)
    digest = canonical_sha256(payload)
    unsigned = {
        "schema": RECEIPT_SCHEMA,
        "decision": decision.value,
        "reason": reason,
        "observation_digest": digest,
        "authority_transfer": False,
    }
    return CacheDecisionReceipt(
        schema=RECEIPT_SCHEMA,
        receipt_id="pci_" + canonical_sha256(unsigned),
        decision=decision,
        reason=reason,
        observation_digest=digest,
        authority_transfer=False,
    )
