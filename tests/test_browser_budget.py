import asyncio
from time import monotonic

import pytest

from aios_tools.browser.budget import BudgetExceeded, BudgetLedger
from aios_tools.browser.runtime import RunPaths, _bounded_cleanup


def test_budget_never_silently_expands():
    ledger = BudgetLedger({"network_requests": 1}, monotonic() + 10)
    ledger.consume("network_requests")
    with pytest.raises(BudgetExceeded):
        ledger.consume("network_requests")


def test_run_paths_block_escape(tmp_path):
    paths = RunPaths(tmp_path)
    assert paths.artifact("trace.zip") == tmp_path.resolve() / "trace.zip"
    with pytest.raises((ValueError, OSError)):
        paths.artifact("../outside.zip")
    with pytest.raises((ValueError, OSError)):
        paths.artifact("/tmp/outside.zip")


def test_cleanup_is_itself_bounded():
    async def run():
        assert await _bounded_cleanup(asyncio.sleep(0), timeout_seconds=0.1) is True
        assert await _bounded_cleanup(asyncio.sleep(1), timeout_seconds=0.01) is False
    asyncio.run(run())
