from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from aios_tools.browser.mutation import (
    MutationLedger,
    MutationPolicyError,
    build_mutation_grant,
)


NOW = datetime(2026, 8, 24, 15, 30, tzinfo=timezone.utc)


def _authority(*, target_url="https://example.com/api/item", method="POST", key="idem-1"):
    return {
        "approval": {
            "approved": True,
            "approved_by": "operator",
            "approval_id": "approval-1",
            "tool": "browser.mutate.request",
            "scope": "global-working-memory",
            "effect_class": "REMOTE_MUTATION_HIGH_IMPACT",
            "target_url": target_url,
            "method": method,
            "idempotency_key": key,
            "one_shot": True,
            "high_impact_ack": True,
            "expires_at": (NOW + timedelta(minutes=5)).isoformat(),
        }
    }


def _grant(**changes):
    target = changes.get("target_url", "https://example.com/api/item")
    method = changes.get("method", "POST")
    key = changes.get("key", "idem-1")
    authority = _authority(target_url=target, method=method, key=key)
    return build_mutation_grant(
        request_id="request-1",
        tool="browser.mutate.request",
        scope="global-working-memory",
        effect_class="REMOTE_MUTATION_HIGH_IMPACT",
        payload={"url": target, "method": method, "idempotency_key": key},
        authority_context=authority,
        now=NOW,
    )


def test_mutation_without_approval_blocks():
    with pytest.raises(MutationPolicyError) as exc:
        build_mutation_grant(
            request_id="request-1",
            tool="browser.mutate.request",
            scope="global-working-memory",
            effect_class="REMOTE_MUTATION_HIGH_IMPACT",
            payload={"url": "https://example.com/api/item", "method": "POST", "idempotency_key": "idem-1"},
            authority_context={},
            now=NOW,
        )
    assert exc.value.code == "APPROVAL_REQUIRED"


@pytest.mark.parametrize("field,value", [
    ("tool", "other.tool"),
    ("scope", "other-scope"),
    ("effect_class", "READ_NETWORK"),
    ("target_url", "https://example.com/api/other"),
    ("method", "DELETE"),
    ("idempotency_key", "other-key"),
])
def test_mutation_approval_exact_binding(field, value):
    authority = _authority()
    authority["approval"][field] = value
    with pytest.raises(MutationPolicyError) as exc:
        build_mutation_grant(
            request_id="request-1",
            tool="browser.mutate.request",
            scope="global-working-memory",
            effect_class="REMOTE_MUTATION_HIGH_IMPACT",
            payload={"url": "https://example.com/api/item", "method": "POST", "idempotency_key": "idem-1"},
            authority_context=authority,
            now=NOW,
        )
    assert exc.value.code == "APPROVAL_SCOPE_MISMATCH"


def test_high_impact_requires_ack():
    authority = _authority()
    authority["approval"]["high_impact_ack"] = False
    with pytest.raises(MutationPolicyError) as exc:
        build_mutation_grant(
            request_id="request-1",
            tool="browser.mutate.request",
            scope="global-working-memory",
            effect_class="REMOTE_MUTATION_HIGH_IMPACT",
            payload={"url": "https://example.com/api/item", "method": "POST", "idempotency_key": "idem-1"},
            authority_context=authority,
            now=NOW,
        )
    assert exc.value.code == "APPROVAL_REQUIRED"


def test_mutation_permit_is_one_shot():
    grant = _grant()
    grant.consume(target_url="https://example.com/api/item", method="POST", idempotency_key="idem-1", now=NOW)
    with pytest.raises(MutationPolicyError) as exc:
        grant.consume(target_url="https://example.com/api/item", method="POST", idempotency_key="idem-1", now=NOW)
    assert exc.value.code == "MUTATION_PERMIT_CONSUMED"


def test_mutation_duplicate_idempotency_blocks(tmp_path):
    ledger = MutationLedger(tmp_path / "ledger.sqlite3")
    first = _grant()
    ledger.reserve(first, now=NOW)
    second = _grant()
    with pytest.raises(MutationPolicyError) as exc:
        ledger.reserve(second, now=NOW)
    assert exc.value.code == "MUTATION_DUPLICATE_BLOCKED"


def test_mutation_unknown_state_remains_reserved(tmp_path):
    ledger = MutationLedger(tmp_path / "ledger.sqlite3")
    grant = _grant()
    ledger.reserve(grant, now=NOW)
    ledger.mark(grant.idempotency_key, "MUTATION_STATE_UNKNOWN", now=NOW)
    assert ledger.status(grant.idempotency_key) == "MUTATION_STATE_UNKNOWN"
    with pytest.raises(MutationPolicyError):
        ledger.reserve(_grant(), now=NOW)
