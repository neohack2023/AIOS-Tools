from __future__ import annotations

from dataclasses import dataclass
import hashlib
from pathlib import Path
import re
import secrets
import shutil
import time

from .session import SessionValidationError


_PROFILE_REF_RE = re.compile(r"^bp_[0-9a-f]{64}$")
_LOGICAL_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,63}$")


def _known_personal_browser_roots(home: Path) -> tuple[Path, ...]:
    return tuple(
        (home / relative).resolve(strict=False)
        for relative in (
            "AppData/Local/Google/Chrome/User Data",
            "AppData/Local/Microsoft/Edge/User Data",
            "Library/Application Support/Google/Chrome",
            "Library/Application Support/Microsoft Edge",
            ".config/google-chrome",
            ".config/chromium",
            ".config/microsoft-edge",
        )
    )


def _inside_or_equal(candidate: Path, root: Path) -> bool:
    try:
        candidate.relative_to(root)
        return True
    except ValueError:
        return False


def assert_not_personal_browser_profile(path: Path, *, home: Path) -> None:
    candidate = path.resolve(strict=False)
    for personal_root in _known_personal_browser_roots(home.resolve(strict=False)):
        if _inside_or_equal(candidate, personal_root) or _inside_or_equal(personal_root, candidate):
            raise SessionValidationError(
                "DEFAULT_BROWSER_PROFILE_REJECTED",
                "personal/default browser profile locations are not admitted for AIOS automation",
            )


@dataclass(frozen=True, slots=True)
class AutomationProfileRef:
    value: str

    def __post_init__(self) -> None:
        if not _PROFILE_REF_RE.fullmatch(self.value):
            raise ValueError("automation profile ref must be opaque")

    @classmethod
    def new(cls) -> "AutomationProfileRef":
        return cls(f"bp_{secrets.token_hex(32)}")

    def fingerprint(self) -> str:
        return hashlib.sha256(self.value.encode("ascii")).hexdigest()


@dataclass(frozen=True, slots=True)
class AutomationProfileHandle:
    profile_ref: AutomationProfileRef
    logical_profile_id: str
    directory: Path
    runtime_root: Path

    def __post_init__(self) -> None:
        if not _LOGICAL_ID_RE.fullmatch(self.logical_profile_id):
            raise ValueError("logical automation profile id is invalid")
        resolved_root = self.runtime_root.resolve(strict=True)
        resolved_directory = self.directory.resolve(strict=True)
        try:
            resolved_directory.relative_to(resolved_root)
        except ValueError as exc:
            raise ValueError("automation profile escaped runtime root") from exc

    def public_receipt(self) -> dict[str, object]:
        return {
            "profile_ref_fingerprint": self.profile_ref.fingerprint(),
            "logical_profile_id": self.logical_profile_id,
            "runtime_owned": True,
            "promotable": False,
            "cloud_sync_allowed": False,
            "personal_browser_profile": False,
            "authority_transfer": False,
        }


class AutomationProfileAllocator:
    """Allocate dedicated AIOS-owned browser profiles under one trusted runtime root."""

    def __init__(
        self,
        runtime_root: Path,
        *,
        home: Path | None = None,
        forbidden_sync_roots: tuple[Path, ...] = (),
    ) -> None:
        if not runtime_root.exists() or not runtime_root.is_dir():
            raise ValueError("automation profile runtime root must already exist")
        self._root = runtime_root.resolve(strict=True)
        self._home = (home or Path.home()).resolve(strict=False)
        assert_not_personal_browser_profile(self._root, home=self._home)
        for sync_root in forbidden_sync_roots:
            resolved_sync = sync_root.resolve(strict=False)
            if _inside_or_equal(self._root, resolved_sync) or _inside_or_equal(resolved_sync, self._root):
                raise SessionValidationError(
                    "AUTOMATION_PROFILE_SYNC_ROOT_REJECTED",
                    "automation browser profiles may not live in configured cloud/sync roots",
                )

    @property
    def runtime_root(self) -> Path:
        return self._root

    def allocate(self, logical_profile_id: str) -> AutomationProfileHandle:
        if not _LOGICAL_ID_RE.fullmatch(logical_profile_id):
            raise ValueError("logical automation profile id is invalid")
        profile_ref = AutomationProfileRef.new()
        candidate = self._root / f"profile-{profile_ref.value[3:19]}"
        candidate.mkdir(mode=0o700, parents=False, exist_ok=False)
        resolved = candidate.resolve(strict=True)
        try:
            resolved.relative_to(self._root)
        except ValueError as exc:
            shutil.rmtree(candidate, ignore_errors=True)
            raise SessionValidationError(
                "AUTOMATION_PROFILE_PATH_ESCAPE",
                "automation profile path escaped the admitted runtime root",
            ) from exc
        assert_not_personal_browser_profile(resolved, home=self._home)
        return AutomationProfileHandle(
            profile_ref=profile_ref,
            logical_profile_id=logical_profile_id,
            directory=resolved,
            runtime_root=self._root,
        )

    def purge(self, handle: AutomationProfileHandle) -> bool:
        resolved = handle.directory.resolve(strict=False)
        try:
            resolved.relative_to(self._root)
        except ValueError as exc:
            raise SessionValidationError(
                "AUTOMATION_PROFILE_PATH_ESCAPE",
                "automation profile purge target escaped runtime root",
            ) from exc
        if not resolved.exists():
            return False
        shutil.rmtree(resolved)
        return True


@dataclass(frozen=True, slots=True)
class AutomationProfileLease:
    profile_ref: AutomationProfileRef
    owner_execution_id: str
    expires_monotonic: float

    def expired(self, now_monotonic: float) -> bool:
        return now_monotonic >= self.expires_monotonic


class AutomationProfileLeaseRegistry:
    """Exclusive monotonic lease for persistent automation profiles."""

    def __init__(self) -> None:
        self._leases: dict[str, AutomationProfileLease] = {}

    def acquire(
        self,
        handle: AutomationProfileHandle,
        *,
        owner_execution_id: str,
        ttl_seconds: float,
        now_monotonic: float | None = None,
    ) -> AutomationProfileLease:
        if not owner_execution_id or any(ch.isspace() for ch in owner_execution_id):
            raise ValueError("profile lease owner must be a compact execution identifier")
        if ttl_seconds <= 0:
            raise ValueError("profile lease ttl must be positive")
        now = time.monotonic() if now_monotonic is None else now_monotonic
        current = self._leases.get(handle.profile_ref.value)
        if current is not None and not current.expired(now):
            raise SessionValidationError(
                "AUTOMATION_PROFILE_LEASE_CONFLICT",
                "automation browser profile is already leased",
            )
        lease = AutomationProfileLease(
            profile_ref=handle.profile_ref,
            owner_execution_id=owner_execution_id,
            expires_monotonic=now + ttl_seconds,
        )
        self._leases[handle.profile_ref.value] = lease
        return lease

    def release(self, lease: AutomationProfileLease) -> bool:
        current = self._leases.get(lease.profile_ref.value)
        if current != lease:
            return False
        del self._leases[lease.profile_ref.value]
        return True

    def recover_stale(self, *, now_monotonic: float | None = None) -> int:
        now = time.monotonic() if now_monotonic is None else now_monotonic
        stale = [ref for ref, lease in self._leases.items() if lease.expired(now)]
        for ref in stale:
            del self._leases[ref]
        return len(stale)
