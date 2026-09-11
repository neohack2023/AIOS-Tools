"""Offline RCV01 diagnostic. Supplied attestations are NOT execution authority."""

from copy import deepcopy


_FIELDS = {
    "scope", "workflow", "envelope", "prefix", "artifacts", "receipts",
    "specialists", "evidence", "evidence_current", "ambiguous", "complete",
    "next_valid", "suffix_invalid", "recovery_available", "recovery_used",
    "retry_count", "retry_limit",
}
_BOOLS = {
    "evidence_current", "ambiguous", "complete", "next_valid",
    "suffix_invalid", "recovery_available", "recovery_used",
}
_LISTS = {"prefix", "artifacts", "receipts", "specialists", "evidence"}


def _valid(value):
    if type(value) is not dict or set(value) != _FIELDS:
        return False
    if value["scope"] != "global-working-memory":
        return False
    if any(type(value[k]) is not str or not value[k].strip()
           for k in ("workflow", "envelope")):
        return False
    if any(type(value[k]) is not bool for k in _BOOLS):
        return False
    for key in _LISTS:
        items = value[key]
        if type(items) is not list or any(
            type(item) is not str or not item.strip() for item in items
        ):
            return False
        if len(items) != len(set(items)):
            return False
    return all(type(value[k]) is int and value[k] >= 0
               for k in ("retry_count", "retry_limit"))


def evaluate_continuation(previous, proposed):
    """Recommend, never execute. Envelope IDs must be externally content-bound.

    Snapshots represent the SAME completed boundary: proposed may change only
    the unexecuted continuation. Revalidate with a new pair after every step.
    Specialist IDs enumerate the entire chain, not just active participants.
    """
    def result(action, reason):
        return {"action": action, "reason": reason,
                "authority_transfer": False, "execution_authorized": False,
                "preserved_boundary": deepcopy(previous) if _valid(previous) else None}

    if not _valid(previous) or not _valid(proposed):
        return result("BLOCK", "INVALID_PACKET")
    for key in ("scope", "workflow", "envelope", "prefix", "artifacts", "receipts",
                "retry_limit", "retry_count", "recovery_used"):
        if previous[key] != proposed[key]:
            return result("BLOCK", "BOUNDARY_CHANGED")
    if not set(previous["specialists"]).issubset(proposed["specialists"]):
        return result("BLOCK", "SPECIALIST_HISTORY_DROPPED")
    if len(set(previous["specialists"]) | set(proposed["specialists"])) > 2:
        return result("BLOCK", "SPECIALIST_CEILING")
    if (not proposed["evidence"] or not proposed["evidence_current"]
            or proposed["ambiguous"]):
        return result("BLOCK", "INSUFFICIENT_CURRENT_EVIDENCE")
    if proposed["complete"]:
        return result("STOP_COMPLETE", "CALLER_ATTESTED_COMPLETION")
    if proposed["retry_count"] >= proposed["retry_limit"]:
        return result("BLOCK", "RETRY_LIMIT")
    if proposed["next_valid"] and not proposed["suffix_invalid"]:
        return result("RETAIN_NEXT", "VALID_CONTINUATION")
    if proposed["recovery_available"] and not proposed["recovery_used"]:
        return result("INSERT_BOUNDED_RECOVERY", "ONE_LOCAL_RECOVERY")
    if proposed["suffix_invalid"]:
        return result("REPLACE_INVALID_SUFFIX", "INVALID_UNEXECUTED_SUFFIX")
    return result("BLOCK", "NO_LAWFUL_CONTINUATION")
