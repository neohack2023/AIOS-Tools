from copy import deepcopy

import pytest

from aios_tools.experimental.route_continuation import evaluate_continuation


def packet():
    return dict(scope="global-working-memory", workflow="workflow-v1",
                envelope="frozen-envelope-digest", prefix=["step-1"],
                artifacts=["artifact-digest"], receipts=["receipt-1"],
                specialists=["one"], evidence=["observation-1"],
                evidence_current=True, ambiguous=False, complete=False,
                next_valid=True, suffix_invalid=False, recovery_available=False,
                recovery_used=False, retry_count=0, retry_limit=2)


@pytest.mark.parametrize("change,expected", [
    ({}, "RETAIN_NEXT"),
    ({"complete": True}, "STOP_COMPLETE"),
    ({"next_valid": False, "recovery_available": True}, "INSERT_BOUNDED_RECOVERY"),
    ({"next_valid": False, "suffix_invalid": True}, "REPLACE_INVALID_SUFFIX"),
    ({"ambiguous": True}, "BLOCK"),
    ({"evidence_current": False}, "BLOCK"),
    ({"evidence": []}, "BLOCK"),
    ({"specialists": ["one", "two", "three"]}, "BLOCK"),
    ({"envelope": "wider-envelope"}, "BLOCK"),
    ({"prefix": []}, "BLOCK"),
    ({"artifacts": ["replacement"]}, "BLOCK"),
    ({"receipts": []}, "BLOCK"),
    ({"retry_limit": 99}, "BLOCK"),
    ({"specialists": ["two"]}, "BLOCK"),
    ({"next_valid": False}, "BLOCK"),
])
def test_actions(change, expected):
    old = packet()
    new = dict(old, **change)
    before = deepcopy((old, new))
    got = evaluate_continuation(old, new)
    assert got["action"] == expected
    assert got["authority_transfer"] is False
    assert got["execution_authorized"] is False
    assert (old, new) == before
    got["preserved_boundary"]["prefix"].append("not-shared")
    assert (old, new) == before


@pytest.mark.parametrize("field", list(packet()))
def test_missing_fields_fail_closed(field):
    bad = packet()
    del bad[field]
    assert evaluate_continuation(packet(), bad)["action"] == "BLOCK"


@pytest.mark.parametrize("change", [
    {"complete": "false"}, {"retry_count": True}, {"retry_limit": -1},
    {"specialists": ["one", "one"]}, {"evidence": [None]},
    {"scope": "sibling"}, {"unknown": True}, {"envelope": ""},
])
def test_malformed(change):
    assert evaluate_continuation(packet(), dict(packet(), **change))["action"] == "BLOCK"


def test_no_repeat_recovery_and_no_retry_reset():
    old = dict(packet(), recovery_used=True, next_valid=False)
    new = dict(old, recovery_available=True)
    assert evaluate_continuation(old, new)["action"] == "BLOCK"
    new["recovery_used"] = False
    assert evaluate_continuation(old, new)["action"] == "BLOCK"
    old = dict(packet(), retry_count=2)
    assert evaluate_continuation(old, old)["action"] == "BLOCK"
    assert evaluate_continuation(old, dict(old, retry_count=0))["action"] == "BLOCK"


def test_completion_never_bypasses_envelope():
    assert evaluate_continuation(packet(), dict(packet(), complete=True,
                                envelope="widened"))["action"] == "BLOCK"


@pytest.mark.parametrize("bad", [None, [], "packet", 1])
def test_nonobjects(bad):
    assert evaluate_continuation(bad, packet())["action"] == "BLOCK"
