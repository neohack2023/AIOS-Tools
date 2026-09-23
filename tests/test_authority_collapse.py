import pytest

from aios_tools.experimental.authority_collapse import (
    AuthorityClass,
    AuthorityCollapseError,
    ClaimObservation,
    ClaimUse,
    GateDecision,
    GateObservation,
    GateType,
    evaluate_claim,
    evaluate_gate,
)


def claim(authority_class, **kwargs):
    values = dict(
        source_id="source-1",
        source_revision="rev-1",
        authority_owner="owner-1",
        authority_domain="domain-a",
        requested_domain="domain-a",
        authority_class=authority_class,
    )
    values.update(kwargs)
    return ClaimObservation(**values)


def gate(gate_type, **kwargs):
    values = dict(
        gate_id="gate-1",
        gate_type=gate_type,
        bound_revision="head-a",
        current_revision="head-a",
        policy_id="policy-1",
        policy_revision="p1",
        current_policy_revision="p1",
        result_pass=True,
        producer_identity="producer",
        reviewer_identity="reviewer",
    )
    values.update(kwargs)
    return GateObservation(**values)


@pytest.mark.parametrize(
    ("observation", "expected"),
    [
        (claim(AuthorityClass.AUTHORITATIVE_CURRENT), ClaimUse.CURRENT_STATE),
        (
            claim(
                AuthorityClass.AUTHORITATIVE_CURRENT,
                requested_domain="domain-b",
            ),
            ClaimUse.BLOCK,
        ),
        (
            claim(
                AuthorityClass.AUTHORITATIVE_SUPERSEDED,
                supersession_link="source-2",
            ),
            ClaimUse.HISTORICAL_ONLY,
        ),
        (
            claim(AuthorityClass.AUTHORITATIVE_SUPERSEDED),
            ClaimUse.BLOCK,
        ),
        (claim(AuthorityClass.RESEARCH_ONLY), ClaimUse.EVIDENCE_ONLY),
        (
            claim(AuthorityClass.CONVERSATION_EVIDENCE),
            ClaimUse.TASK_ONLY,
        ),
        (
            claim(AuthorityClass.SHADOW_NONAUTHORITY),
            ClaimUse.ROUTING_ONLY,
        ),
        (claim(AuthorityClass.AUTHORITY_CONFLICT), ClaimUse.BLOCK),
    ],
)
def test_claim_authority_classes(observation, expected):
    result = evaluate_claim(observation)
    assert result.decision == expected.value
    assert result.authority_transfer is False


@pytest.mark.parametrize(
    ("observation", "expected"),
    [
        (gate(GateType.ADVISORY), GateDecision.EVIDENCE_ONLY),
        (gate(GateType.WORKFLOW_APPROVAL), GateDecision.GATE_PASS),
        (
            gate(
                GateType.WORKFLOW_APPROVAL,
                current_revision="head-b",
            ),
            GateDecision.STALE,
        ),
        (
            gate(
                GateType.WORKFLOW_APPROVAL,
                current_policy_revision="p2",
            ),
            GateDecision.STALE,
        ),
        (
            gate(
                GateType.WORKFLOW_APPROVAL,
                reviewer_identity="producer",
            ),
            GateDecision.BLOCK,
        ),
        (
            gate(
                GateType.WORKFLOW_APPROVAL,
                approval_scope_matches=False,
            ),
            GateDecision.BLOCK,
        ),
        (
            gate(
                GateType.WORKFLOW_APPROVAL,
                capability_enabled=False,
            ),
            GateDecision.EVIDENCE_ONLY,
        ),
        (gate(GateType.SECURITY_SCAN), GateDecision.GATE_PASS),
        (
            gate(
                GateType.SECURITY_SCAN,
                scan_complete=False,
            ),
            GateDecision.BLOCK,
        ),
        (
            gate(
                GateType.SECURITY_SCAN,
                result_pass=False,
            ),
            GateDecision.BLOCK,
        ),
        (
            gate(
                GateType.SECURITY_SCAN,
                current_revision="head-b",
            ),
            GateDecision.STALE,
        ),
        (
            gate(
                GateType.SECURITY_SCAN,
                result_pass=False,
                bypass_used=True,
                bypass_actor="admin",
                bypass_authority_source="ruleset-bypass",
            ),
            GateDecision.BYPASS,
        ),
    ],
)
def test_gate_evidence_is_revision_and_policy_bound(observation, expected):
    result = evaluate_gate(observation)
    assert result.decision == expected.value
    assert result.authority_transfer is False


def test_bypass_without_provenance_blocks():
    result = evaluate_gate(
        gate(
            GateType.SECURITY_SCAN,
            result_pass=False,
            bypass_used=True,
            bypass_actor=None,
            bypass_authority_source=None,
        )
    )
    assert result.decision == GateDecision.BLOCK.value


def test_missing_source_revision_fails_closed():
    with pytest.raises(
        AuthorityCollapseError,
        match="source_revision_required",
    ):
        evaluate_claim(
            claim(
                AuthorityClass.RESEARCH_ONLY,
                source_revision="",
            )
        )


def test_receipts_are_deterministic():
    observation = gate(GateType.WORKFLOW_APPROVAL)
    assert evaluate_gate(observation) == evaluate_gate(observation)
