"""Offline execution-completion evaluator.

Caller-supplied trajectory facts are evidence only. This module does not execute,
authorize, schedule, or inspect hidden reasoning.
"""

from copy import deepcopy


_CONTRACT_FIELDS = {
    "contract_version",
    "scope_key",
    "workflow_id",
    "contract_id",
    "objective",
    "required_deliverables",
    "required_events",
    "forbidden_events",
    "required_order",
    "success_predicates",
    "verification_owner",
    "max_steps",
}
_TRAJECTORY_FIELDS = {
    "scope_key",
    "workflow_id",
    "contract_id",
    "deliverables",
    "events",
    "predicate_results",
    "verification_owner",
    "terminal",
    "step_count",
}
_PREDICATE_STATES = {"PASS", "FAIL", "UNKNOWN"}


def _is_nonempty_string(value):
    return type(value) is str and bool(value.strip())


def _valid_string_list(value, *, unique=True):
    if type(value) is not list:
        return False
    if any(not _is_nonempty_string(item) for item in value):
        return False
    return not unique or len(value) == len(set(value))


def _valid_contract(contract):
    if type(contract) is not dict or set(contract) != _CONTRACT_FIELDS:
        return False
    if contract["contract_version"] != "0.1":
        return False
    if contract["scope_key"] != "global-working-memory":
        return False
    if any(
        not _is_nonempty_string(contract[key])
        for key in ("workflow_id", "contract_id", "objective", "verification_owner")
    ):
        return False
    for key in (
        "required_deliverables",
        "required_events",
        "forbidden_events",
        "success_predicates",
    ):
        if not _valid_string_list(contract[key], unique=True):
            return False
    if type(contract["required_order"]) is not list:
        return False
    seen_pairs = set()
    required_events = set(contract["required_events"])
    for pair in contract["required_order"]:
        if type(pair) is not dict or set(pair) != {"before", "after"}:
            return False
        before = pair["before"]
        after = pair["after"]
        if not _is_nonempty_string(before) or not _is_nonempty_string(after):
            return False
        if before == after or before not in required_events or after not in required_events:
            return False
        pair_key = (before, after)
        if pair_key in seen_pairs:
            return False
        seen_pairs.add(pair_key)
    return type(contract["max_steps"]) is int and contract["max_steps"] >= 0


def _valid_trajectory(trajectory, contract):
    if type(trajectory) is not dict or set(trajectory) != _TRAJECTORY_FIELDS:
        return False
    if trajectory["scope_key"] != "global-working-memory":
        return False
    if any(
        not _is_nonempty_string(trajectory[key])
        for key in ("workflow_id", "contract_id", "verification_owner")
    ):
        return False
    if not _valid_string_list(trajectory["deliverables"], unique=True):
        return False
    if not _valid_string_list(trajectory["events"], unique=False):
        return False
    predicates = trajectory["predicate_results"]
    if type(predicates) is not dict:
        return False
    if set(predicates) != set(contract["success_predicates"]):
        return False
    if any(value not in _PREDICATE_STATES for value in predicates.values()):
        return False
    if type(trajectory["terminal"]) is not bool:
        return False
    return type(trajectory["step_count"]) is int and trajectory["step_count"] >= 0


def evaluate_completion(contract, trajectory):
    """Evaluate observable completion evidence without granting authority."""

    def result(verdict, reason, *, missing_deliverables=None, missing_events=None,
               failed_predicates=None, unknown_predicates=None):
        return {
            "verdict": verdict,
            "reason": reason,
            "missing_deliverables": missing_deliverables or [],
            "missing_events": missing_events or [],
            "failed_predicates": failed_predicates or [],
            "unknown_predicates": unknown_predicates or [],
            "authority_transfer": False,
            "execution_authorized": False,
        }

    if not _valid_contract(contract):
        return result("BLOCKED", "INVALID_CONTRACT")
    if not _valid_trajectory(trajectory, contract):
        return result("BLOCKED", "INVALID_TRAJECTORY")

    identity_fields = ("scope_key", "workflow_id", "contract_id", "verification_owner")
    if any(contract[key] != trajectory[key] for key in identity_fields):
        return result("BLOCKED", "IDENTITY_OR_VERIFIER_MISMATCH")

    events = trajectory["events"]
    if any(event in set(contract["forbidden_events"]) for event in events):
        return result("FAIL", "FORBIDDEN_EVENT")

    if trajectory["step_count"] > contract["max_steps"]:
        return result("FAIL", "STEP_BUDGET_EXCEEDED")

    for pair in contract["required_order"]:
        before = pair["before"]
        after = pair["after"]
        if before in events and after in events and events.index(before) >= events.index(after):
            return result("FAIL", "EVENT_ORDER_VIOLATION")

    failed = sorted(
        key for key, value in trajectory["predicate_results"].items() if value == "FAIL"
    )
    if failed:
        return result("FAIL", "PREDICATE_FAILED", failed_predicates=failed)

    required_deliverables = set(contract["required_deliverables"])
    observed_deliverables = set(trajectory["deliverables"])
    required_events = set(contract["required_events"])
    observed_events = set(events)
    missing_deliverables = sorted(required_deliverables - observed_deliverables)
    missing_events = sorted(required_events - observed_events)
    unknown = sorted(
        key for key, value in trajectory["predicate_results"].items() if value == "UNKNOWN"
    )

    if missing_deliverables or missing_events or unknown:
        verdict = "FAIL" if trajectory["terminal"] else "PARTIAL"
        reason = "TERMINAL_INCOMPLETE" if trajectory["terminal"] else "OBLIGATIONS_PENDING"
        return result(
            verdict,
            reason,
            missing_deliverables=missing_deliverables,
            missing_events=missing_events,
            unknown_predicates=unknown,
        )

    if not trajectory["terminal"]:
        return result("PARTIAL", "SATISFIED_NOT_TERMINAL")

    return result("PASS", "CONTRACT_SATISFIED")
