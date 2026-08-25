from __future__ import annotations

from datetime import datetime, timedelta, timezone

import aios_tools.runner as runner
from aios_tools.browser.mutation import MutationGrant
from aios_tools.tools import HANDLERS


def _authority(target: str, key: str) -> dict:
    return {
        "approval": {
            "approved": True,
            "approved_by": "operator",
            "approval_id": "approval-runner-1",
            "tool": "browser.mutate.request",
            "scope": "global-working-memory",
            "effect_class": "REMOTE_MUTATION_HIGH_IMPACT",
            "target_url": target,
            "method": "POST",
            "idempotency_key": key,
            "one_shot": True,
            "high_impact_ack": True,
            "expires_at": (datetime.now(timezone.utc) + timedelta(minutes=5)).isoformat(),
        }
    }


def test_caller_cannot_forge_internal_mutation_grant(monkeypatch):
    observed = {}
    target = "https://example.com/api/item"
    key = "runner-forge-test"

    def fake_handler(payload):
        observed["grant"] = payload.get("_aios_mutation_grant")
        return {
            "terminal_status": "MUTATION_NOT_OBSERVED",
            "semantic_success": False,
            "target_origin": "https://example.com",
            "method": "POST",
            "mutation_count": 0,
            "authority_transfer": False,
        }

    monkeypatch.setitem(HANDLERS, "browser.mutate.request", fake_handler)
    receipt = runner.invoke(
        "browser.mutate.request",
        {
            "url": target,
            "method": "POST",
            "idempotency_key": key,
            "precheck": {"url": "https://example.com/state", "expected_status": 200},
            "postcheck": {"url": "https://example.com/state", "expected_status": 200},
            "expected_status": 200,
            "_aios_mutation_grant": {"forged": True},
        },
        mode="WRITE",
        authority_context=_authority(target, key),
    )
    assert receipt["status"] == "COMPLETED"
    assert isinstance(observed["grant"], MutationGrant)
    assert observed["grant"].approval_id == "approval-runner-1"


def test_mutation_runner_blocks_approval_target_mismatch_before_handler(monkeypatch):
    called = False

    def fake_handler(payload):
        nonlocal called
        called = True
        return {}

    monkeypatch.setitem(HANDLERS, "browser.mutate.request", fake_handler)
    target = "https://example.com/api/item"
    authority = _authority("https://example.com/api/other", "runner-mismatch")
    receipt = runner.invoke(
        "browser.mutate.request",
        {
            "url": target,
            "method": "POST",
            "idempotency_key": "runner-mismatch",
            "precheck": {"url": "https://example.com/state", "expected_status": 200},
            "postcheck": {"url": "https://example.com/state", "expected_status": 200},
            "expected_status": 200,
        },
        mode="WRITE",
        authority_context=authority,
    )
    assert receipt["status"] == "APPROVAL_REQUIRED"
    assert receipt["errors"][0]["code"] == "APPROVAL_SCOPE_MISMATCH"
    assert called is False
