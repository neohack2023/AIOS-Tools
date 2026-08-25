from __future__ import annotations

import pytest

from aios_tools.browser.mutation import MutationLedger
from aios_tools.tools import _mutation_failure_truth


class _Ledger:
    def __init__(self, status: str | None):
        self._status = status

    def status(self, key: str) -> str | None:
        assert key == "idem-truth"
        return self._status


def _boom(payload):
    raise RuntimeError("fixture secret detail must not escape")


def test_unknown_remote_effect_survives_executor_exception(monkeypatch):
    monkeypatch.setattr(MutationLedger, "default", classmethod(lambda cls: _Ledger("MUTATION_STATE_UNKNOWN")))
    result = _mutation_failure_truth(
        {
            "url": "https://example.com/api/item?secret=hidden",
            "method": "POST",
            "idempotency_key": "idem-truth",
        },
        _boom,
    )
    assert result == {
        "terminal_status": "MUTATION_STATE_UNKNOWN",
        "semantic_success": False,
        "target_origin": "https://example.com",
        "method": "POST",
        "mutation_count": 1,
        "durable_ledger_state": "MUTATION_STATE_UNKNOWN",
        "executor_exception_sanitized": True,
        "authority_transfer": False,
    }
    assert "hidden" not in repr(result)
    assert "fixture secret detail" not in repr(result)


def test_no_effect_executor_exception_is_not_reclassified(monkeypatch):
    monkeypatch.setattr(MutationLedger, "default", classmethod(lambda cls: _Ledger("FAILED_NO_EFFECT")))
    with pytest.raises(RuntimeError, match="fixture secret detail"):
        _mutation_failure_truth(
            {
                "url": "https://example.com/api/item",
                "method": "POST",
                "idempotency_key": "idem-truth",
            },
            _boom,
        )
