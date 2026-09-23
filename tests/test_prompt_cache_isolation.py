import pytest

from aios_tools.experimental.prompt_cache_isolation import (
    CacheDecision,
    CacheObservation,
    decide_cache_use,
)


def obs(**kwargs):
    values = dict(
        request_tenant_hash="tenant-a",
        cache_tenant_hash="tenant-a",
        prefix_match=True,
        system_prompt_match=True,
        tool_definition_match=True,
        policy_revision_match=True,
        ttl_valid=True,
        cache_available=True,
        cache_hit=True,
        freshness_required=False,
        correctness_evidence_current=True,
    )
    values.update(kwargs)
    return CacheObservation(**values)


@pytest.mark.parametrize(
    ("candidate", "expected"),
    [
        (obs(), CacheDecision.REUSE_ALLOWED),
        (
            obs(cache_tenant_hash="tenant-b"),
            CacheDecision.BLOCK_CROSS_TENANT,
        ),
        (
            obs(tool_definition_match=False),
            CacheDecision.MISS_REBUILD,
        ),
        (obs(ttl_valid=False), CacheDecision.MISS_REBUILD),
        (
            obs(
                freshness_required=True,
                correctness_evidence_current=False,
            ),
            CacheDecision.FRESHNESS_EVIDENCE_REQUIRED,
        ),
        (
            obs(
                cache_available=False,
                cache_hit=False,
                cache_tenant_hash=None,
            ),
            CacheDecision.BYPASS_CACHE,
        ),
    ],
)
def test_cache_isolation_matrix(candidate, expected):
    receipt = decide_cache_use(candidate)
    assert receipt.decision == expected
    assert receipt.authority_transfer is False


def test_policy_revision_change_forces_rebuild():
    receipt = decide_cache_use(obs(policy_revision_match=False))
    assert receipt.decision == CacheDecision.MISS_REBUILD


def test_system_prompt_change_forces_rebuild():
    receipt = decide_cache_use(obs(system_prompt_match=False))
    assert receipt.decision == CacheDecision.MISS_REBUILD


def test_receipt_is_deterministic():
    candidate = obs()
    assert decide_cache_use(candidate) == decide_cache_use(candidate)
