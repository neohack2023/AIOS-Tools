from __future__ import annotations

import inspect
from pathlib import Path

import pytest

from aios_tools.browser.profile import (
    AutomationProfileAllocator,
    AutomationProfileLeaseRegistry,
    assert_not_personal_browser_profile,
)
from aios_tools.browser.session import SessionValidationError


def _roots(tmp_path: Path) -> tuple[Path, Path]:
    home = tmp_path / "home"
    runtime = tmp_path / "runtime"
    home.mkdir()
    runtime.mkdir()
    return home, runtime


def test_default_browser_profile_roots_are_rejected(tmp_path):
    home = tmp_path / "home"
    home.mkdir()
    default_chrome = home / ".config" / "google-chrome"
    default_chrome.mkdir(parents=True)
    with pytest.raises(SessionValidationError) as exc:
        assert_not_personal_browser_profile(default_chrome, home=home)
    assert exc.value.code == "DEFAULT_BROWSER_PROFILE_REJECTED"


def test_allocator_rejects_runtime_root_inside_personal_browser_tree(tmp_path):
    home = tmp_path / "home"
    default_edge = home / "AppData" / "Local" / "Microsoft" / "Edge" / "User Data"
    runtime = default_edge / "AIOS"
    runtime.mkdir(parents=True)
    with pytest.raises(SessionValidationError) as exc:
        AutomationProfileAllocator(runtime, home=home)
    assert exc.value.code == "DEFAULT_BROWSER_PROFILE_REJECTED"


def test_automation_profile_allocation_is_contained_under_runtime_root(tmp_path):
    home, runtime = _roots(tmp_path)
    allocator = AutomationProfileAllocator(runtime, home=home)
    handle = allocator.allocate("suno-harvest")
    assert handle.directory.is_dir()
    handle.directory.relative_to(runtime.resolve())
    receipt = handle.public_receipt()
    rendered = repr(receipt)
    assert str(handle.directory) not in rendered
    assert handle.profile_ref.value not in rendered
    assert receipt["runtime_owned"] is True
    assert receipt["promotable"] is False
    assert receipt["cloud_sync_allowed"] is False
    assert receipt["personal_browser_profile"] is False
    assert receipt["authority_transfer"] is False


def test_allocator_has_no_caller_profile_path_parameter(tmp_path):
    parameters = set(inspect.signature(AutomationProfileAllocator.allocate).parameters)
    assert parameters == {"self", "logical_profile_id"}
    assert "path" not in parameters
    assert "user_data_dir" not in parameters
    assert "profile_path" not in parameters


def test_profile_directory_is_not_promotable_and_sync_root_is_rejected(tmp_path):
    home = tmp_path / "home"
    home.mkdir()
    sync_root = tmp_path / "DriveSync"
    runtime = sync_root / "browser-profiles"
    runtime.mkdir(parents=True)
    with pytest.raises(SessionValidationError) as exc:
        AutomationProfileAllocator(runtime, home=home, forbidden_sync_roots=(sync_root,))
    assert exc.value.code == "AUTOMATION_PROFILE_SYNC_ROOT_REJECTED"


def test_persistent_profile_exclusive_lease_blocks_concurrent_reuse(tmp_path):
    home, runtime = _roots(tmp_path)
    allocator = AutomationProfileAllocator(runtime, home=home)
    handle = allocator.allocate("profile-one")
    leases = AutomationProfileLeaseRegistry()
    first = leases.acquire(handle, owner_execution_id="exec-1", ttl_seconds=30, now_monotonic=10)
    with pytest.raises(SessionValidationError) as exc:
        leases.acquire(handle, owner_execution_id="exec-2", ttl_seconds=30, now_monotonic=11)
    assert exc.value.code == "AUTOMATION_PROFILE_LEASE_CONFLICT"
    assert leases.release(first) is True
    second = leases.acquire(handle, owner_execution_id="exec-2", ttl_seconds=30, now_monotonic=20)
    assert second.owner_execution_id == "exec-2"


def test_stale_profile_lease_can_be_recovered(tmp_path):
    home, runtime = _roots(tmp_path)
    handle = AutomationProfileAllocator(runtime, home=home).allocate("profile-one")
    leases = AutomationProfileLeaseRegistry()
    lease = leases.acquire(handle, owner_execution_id="exec-1", ttl_seconds=5, now_monotonic=10)
    assert leases.recover_stale(now_monotonic=14) == 0
    assert leases.recover_stale(now_monotonic=15) == 1
    assert leases.release(lease) is False


def test_profile_purge_is_contained_and_idempotent(tmp_path):
    home, runtime = _roots(tmp_path)
    allocator = AutomationProfileAllocator(runtime, home=home)
    handle = allocator.allocate("profile-one")
    marker = handle.directory / "synthetic.txt"
    marker.write_text("not-a-secret", encoding="utf-8")
    assert allocator.purge(handle) is True
    assert handle.directory.exists() is False
    assert allocator.purge(handle) is False
    assert runtime.exists() is True
