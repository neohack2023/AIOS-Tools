from copy import deepcopy

import pytest

from aios_tools.experimental.next_action_priority import rank_legal_actions


def action(action_id, **changes):
    value = {
        "action_id": action_id,
        "available": True,
        "authority_compatible": True,
        "user_priority": 0,
        "dependency_unblocking": 0,
        "urgency": 0,
        "expected_value": 0,
        "evidence_readiness": 0,
        "risk": 0,
        "cost": 0,
        "reversibility": 0,
        "staleness": 0,
    }
    value.update(changes)
    return value


def packet(actions=None):
    return {
        "policy_version": "0.1",
        "scope_key": "global-working-memory",
        "execution_id": "exec-01",
        "actions": actions if actions is not None else [action("alpha")],
    }


def test_single_legal_action_ranks_without_authority():
    p = packet()
    before = deepcopy(p)
    got = rank_legal_actions(p)
    assert got["status"] == "RANKED"
    assert got["recommended_action"] == "alpha"
    assert got["ranked_actions"] == ["alpha"]
    assert got["authority_transfer"] is False
    assert got["execution_authorized"] is False
    assert p == before


def test_user_priority_dominates_later_factors():
    p = packet([
        action("low-user", user_priority=1, dependency_unblocking=5, urgency=5,
               expected_value=5, evidence_readiness=5, risk=0, cost=0,
               reversibility=5, staleness=5),
        action("high-user", user_priority=2, risk=5, cost=5),
    ])
    assert rank_legal_actions(p)["ranked_actions"] == ["high-user", "low-user"]


def test_dependency_urgency_value_and_evidence_are_lexicographic():
    p = packet([
        action("evidence", evidence_readiness=5),
        action("value", expected_value=1),
        action("urgent", urgency=1),
        action("dependency", dependency_unblocking=1),
    ])
    assert rank_legal_actions(p)["ranked_actions"] == [
        "dependency", "urgent", "value", "evidence"
    ]


def test_lower_risk_then_lower_cost_win_after_positive_factors_tie():
    p = packet([
        action("high-risk", risk=2, cost=0),
        action("low-risk-high-cost", risk=1, cost=5),
        action("low-risk-low-cost", risk=1, cost=1),
    ])
    assert rank_legal_actions(p)["ranked_actions"] == [
        "low-risk-low-cost", "low-risk-high-cost", "high-risk"
    ]


def test_reversibility_then_staleness_then_action_id_break_ties():
    p = packet([
        action("zeta", reversibility=1, staleness=5),
        action("beta", reversibility=2, staleness=1),
        action("alpha", reversibility=2, staleness=1),
        action("aged", reversibility=2, staleness=2),
    ])
    assert rank_legal_actions(p)["ranked_actions"] == ["aged", "alpha", "beta", "zeta"]


def test_ranking_evidence_matches_rank_order():
    p = packet([action("b", user_priority=1), action("a", user_priority=1)])
    got = rank_legal_actions(p)
    assert [row["action_id"] for row in got["ranking_evidence"]] == ["a", "b"]
    assert got["ranking_evidence"][0]["user_priority"] == 1


@pytest.mark.parametrize(
    "actions,reason",
    [
        ([], "EMPTY_ACTION_SET"),
        ([action("a"), action("a")], "DUPLICATE_ACTION_ID"),
        ([action("a", available=False)], "UNAVAILABLE_ACTION_PRESENT"),
        ([action("a", authority_compatible=False)], "AUTHORITY_INCOMPATIBLE_ACTION_PRESENT"),
    ],
)
def test_illegal_or_empty_action_sets_block(actions, reason):
    got = rank_legal_actions(packet(actions))
    assert got["status"] == "BLOCKED"
    assert got["reason"] == reason
    assert got["recommended_action"] is None
    assert got["ranked_actions"] == []


@pytest.mark.parametrize(
    "change",
    [
        {"user_priority": 6},
        {"urgency": -1},
        {"risk": True},
        {"cost": "1"},
        {"action_id": ""},
        {"unknown_factor": 1},
    ],
)
def test_malformed_actions_fail_closed(change):
    bad = action("a")
    bad.update(change)
    got = rank_legal_actions(packet([bad]))
    assert got["status"] == "BLOCKED"
    assert got["reason"] == "INVALID_ACTION"


@pytest.mark.parametrize(
    "change,reason",
    [
        ({"policy_version": "0.2"}, "INVALID_POLICY_VERSION"),
        ({"scope_key": "sibling"}, "INVALID_SCOPE"),
        ({"execution_id": ""}, "INVALID_EXECUTION_ID"),
        ({"extra": True}, "INVALID_PACKET"),
    ],
)
def test_malformed_packets_fail_closed(change, reason):
    p = packet()
    p.update(change)
    got = rank_legal_actions(p)
    assert got["status"] == "BLOCKED"
    assert got["reason"] == reason
