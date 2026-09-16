"""Offline priority policy for actions already admitted by NextAction routing.

This module ranks only. It never creates, authorizes, selects, or executes an action.
"""

from copy import deepcopy


_PACKET_FIELDS = {"policy_version", "scope_key", "execution_id", "actions"}
_ACTION_FIELDS = {
    "action_id",
    "available",
    "authority_compatible",
    "user_priority",
    "dependency_unblocking",
    "urgency",
    "expected_value",
    "evidence_readiness",
    "risk",
    "cost",
    "reversibility",
    "staleness",
}
_FACTOR_FIELDS = (
    "user_priority",
    "dependency_unblocking",
    "urgency",
    "expected_value",
    "evidence_readiness",
    "risk",
    "cost",
    "reversibility",
    "staleness",
)


def _is_nonempty_string(value):
    return type(value) is str and bool(value.strip())


def _valid_action(action):
    if type(action) is not dict or set(action) != _ACTION_FIELDS:
        return False
    if not _is_nonempty_string(action["action_id"]):
        return False
    if type(action["available"]) is not bool or type(action["authority_compatible"]) is not bool:
        return False
    return all(type(action[key]) is int and 0 <= action[key] <= 5 for key in _FACTOR_FIELDS)


def _valid_packet(packet):
    if type(packet) is not dict or set(packet) != _PACKET_FIELDS:
        return False, "INVALID_PACKET"
    if packet["policy_version"] != "0.1":
        return False, "INVALID_POLICY_VERSION"
    if packet["scope_key"] != "global-working-memory":
        return False, "INVALID_SCOPE"
    if not _is_nonempty_string(packet["execution_id"]):
        return False, "INVALID_EXECUTION_ID"
    actions = packet["actions"]
    if type(actions) is not list or not actions:
        return False, "EMPTY_ACTION_SET"
    if any(not _valid_action(action) for action in actions):
        return False, "INVALID_ACTION"
    ids = [action["action_id"] for action in actions]
    if len(ids) != len(set(ids)):
        return False, "DUPLICATE_ACTION_ID"
    if any(not action["available"] for action in actions):
        return False, "UNAVAILABLE_ACTION_PRESENT"
    if any(not action["authority_compatible"] for action in actions):
        return False, "AUTHORITY_INCOMPATIBLE_ACTION_PRESENT"
    return True, None


def _sort_key(action):
    return (
        -action["user_priority"],
        -action["dependency_unblocking"],
        -action["urgency"],
        -action["expected_value"],
        -action["evidence_readiness"],
        action["risk"],
        action["cost"],
        -action["reversibility"],
        -action["staleness"],
        action["action_id"],
    )


def rank_legal_actions(packet):
    """Return deterministic advisory ordering over an already-legal action set."""

    valid, reason = _valid_packet(packet)
    if not valid:
        return {
            "status": "BLOCKED",
            "reason": reason,
            "policy_version": "0.1",
            "recommended_action": None,
            "ranked_actions": [],
            "ranking_evidence": [],
            "authority_transfer": False,
            "execution_authorized": False,
        }

    ranked = sorted((deepcopy(action) for action in packet["actions"]), key=_sort_key)
    evidence = [
        {
            "action_id": action["action_id"],
            **{key: action[key] for key in _FACTOR_FIELDS},
        }
        for action in ranked
    ]
    return {
        "status": "RANKED",
        "reason": "LEGAL_ACTIONS_RANKED",
        "policy_version": packet["policy_version"],
        "recommended_action": ranked[0]["action_id"],
        "ranked_actions": [action["action_id"] for action in ranked],
        "ranking_evidence": evidence,
        "authority_transfer": False,
        "execution_authorized": False,
    }
