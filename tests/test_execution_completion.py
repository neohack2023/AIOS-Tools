from copy import deepcopy

import pytest

from aios_tools.experimental.execution_completion import evaluate_completion


def contract():
    return {
        "contract_version": "0.1",
        "scope_key": "global-working-memory",
        "workflow_id": "workflow-v1",
        "contract_id": "completion-01",
        "objective": "produce and verify one artifact",
        "required_deliverables": ["artifact"],
        "required_events": ["started", "artifact_written", "verified"],
        "forbidden_events": ["unauthorized_write"],
        "required_order": [
            {"before": "started", "after": "artifact_written"},
            {"before": "artifact_written", "after": "verified"},
        ],
        "success_predicates": ["shape", "integrity"],
        "verification_owner": "task-native-verifier-v1",
        "max_steps": 5,
    }


def trajectory():
    return {
        "scope_key": "global-working-memory",
        "workflow_id": "workflow-v1",
        "contract_id": "completion-01",
        "deliverables": ["artifact"],
        "events": ["started", "artifact_written", "verified"],
        "predicate_results": {"shape": "PASS", "integrity": "PASS"},
        "verification_owner": "task-native-verifier-v1",
        "terminal": True,
        "step_count": 3,
    }


def test_complete_terminal_run_passes_without_authority():
    c = contract()
    t = trajectory()
    before = deepcopy((c, t))
    got = evaluate_completion(c, t)
    assert got["verdict"] == "PASS"
    assert got["reason"] == "CONTRACT_SATISFIED"
    assert got["authority_transfer"] is False
    assert got["execution_authorized"] is False
    assert (c, t) == before


def test_satisfied_but_nonterminal_is_partial():
    t = dict(trajectory(), terminal=False)
    got = evaluate_completion(contract(), t)
    assert got["verdict"] == "PARTIAL"
    assert got["reason"] == "SATISFIED_NOT_TERMINAL"


def test_nonterminal_missing_obligations_are_partial():
    t = dict(trajectory(), terminal=False, deliverables=[], events=["started"],
             predicate_results={"shape": "PASS", "integrity": "UNKNOWN"})
    got = evaluate_completion(contract(), t)
    assert got["verdict"] == "PARTIAL"
    assert got["reason"] == "OBLIGATIONS_PENDING"
    assert got["missing_deliverables"] == ["artifact"]
    assert got["missing_events"] == ["artifact_written", "verified"]
    assert got["unknown_predicates"] == ["integrity"]


def test_terminal_missing_obligations_fail():
    t = dict(trajectory(), deliverables=[], events=["started"])
    got = evaluate_completion(contract(), t)
    assert got["verdict"] == "FAIL"
    assert got["reason"] == "TERMINAL_INCOMPLETE"


@pytest.mark.parametrize(
    "change,reason",
    [
        ({"events": ["started", "unauthorized_write", "artifact_written", "verified"]},
         "FORBIDDEN_EVENT"),
        ({"step_count": 6}, "STEP_BUDGET_EXCEEDED"),
        ({"events": ["artifact_written", "started", "verified"]}, "EVENT_ORDER_VIOLATION"),
        ({"predicate_results": {"shape": "FAIL", "integrity": "PASS"}}, "PREDICATE_FAILED"),
    ],
)
def test_failure_conditions(change, reason):
    got = evaluate_completion(contract(), dict(trajectory(), **change))
    assert got["verdict"] == "FAIL"
    assert got["reason"] == reason


@pytest.mark.parametrize(
    "change",
    [
        {"scope_key": "sibling"},
        {"workflow_id": "other-workflow"},
        {"contract_id": "other-contract"},
        {"verification_owner": "other-verifier"},
    ],
)
def test_identity_or_verifier_mismatch_blocks(change):
    got = evaluate_completion(contract(), dict(trajectory(), **change))
    assert got["verdict"] == "BLOCKED"
    assert got["reason"] in {"INVALID_TRAJECTORY", "IDENTITY_OR_VERIFIER_MISMATCH"}


def test_repeated_observable_events_are_allowed():
    t = dict(trajectory(), events=["started", "started", "artifact_written", "verified"])
    assert evaluate_completion(contract(), t)["verdict"] == "PASS"


def test_reasoning_content_is_not_admitted():
    t = dict(trajectory(), hidden_reasoning="should never be accepted")
    got = evaluate_completion(contract(), t)
    assert got["verdict"] == "BLOCKED"
    assert got["reason"] == "INVALID_TRAJECTORY"


@pytest.mark.parametrize(
    "mutator",
    [
        lambda c: {**c, "required_events": ["started", "started"]},
        lambda c: {**c, "required_order": [{"before": "started", "after": "not-declared"}]},
        lambda c: {**c, "max_steps": True},
        lambda c: {k: v for k, v in c.items() if k != "objective"},
    ],
)
def test_malformed_contracts_fail_closed(mutator):
    got = evaluate_completion(mutator(contract()), trajectory())
    assert got["verdict"] == "BLOCKED"
    assert got["reason"] == "INVALID_CONTRACT"


@pytest.mark.parametrize(
    "change",
    [
        {"predicate_results": {"shape": "PASS"}},
        {"predicate_results": {"shape": "PASS", "integrity": "MAYBE"}},
        {"step_count": True},
        {"terminal": "true"},
        {"deliverables": ["artifact", "artifact"]},
    ],
)
def test_malformed_trajectories_fail_closed(change):
    got = evaluate_completion(contract(), dict(trajectory(), **change))
    assert got["verdict"] == "BLOCKED"
    assert got["reason"] == "INVALID_TRAJECTORY"
