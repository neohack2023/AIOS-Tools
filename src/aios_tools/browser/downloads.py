from __future__ import annotations

from dataclasses import asdict, dataclass
from hashlib import sha256
import mimetypes
import os
from pathlib import Path
import re
import stat
from time import monotonic
from typing import Callable, Iterable, Iterator
from uuid import uuid4

from .evidence import minimize_url
from .origin import NormalizedOrigin


class DownloadQuarantineError(RuntimeError):
    pass


class DownloadTransferCancelled(DownloadQuarantineError):
    pass


@dataclass(frozen=True, slots=True)
class DownloadLimits:
    max_downloads: int
    max_file_bytes: int
    max_aggregate_bytes: int
    max_elapsed_seconds: float = 60.0

    def __post_init__(self) -> None:
        if (
            self.max_downloads < 1
            or self.max_file_bytes < 1
            or self.max_aggregate_bytes < 1
            or self.max_elapsed_seconds <= 0
        ):
            raise ValueError("download limits must be positive")
        if self.max_file_bytes > self.max_aggregate_bytes:
            raise ValueError("per-file download limit cannot exceed aggregate limit")


@dataclass(frozen=True, slots=True)
class DownloadRecord:
    state: str
    source_origin: str
    source_path_digest: str
    suggested_filename: str
    content_type: str | None
    declared_size: int | None
    observed_bytes: int
    sha256: str | None
    quarantine_name: str | None
    promoted: bool
    mime_extension_mismatch: bool | None
    reason: str | None

    def to_dict(self) -> dict:
        return asdict(self)


_WINDOWS_DEVICE_NAMES = {
    "CON",
    "PRN",
    "AUX",
    "NUL",
    *(f"COM{i}" for i in range(1, 10)),
    *(f"LPT{i}" for i in range(1, 10)),
}
_SAFE_CHARS = re.compile(r"[^A-Za-z0-9._ -]+")


def _is_reparse_point(path: Path) -> bool:
    info = path.lstat()
    if stat.S_ISLNK(info.st_mode):
        return True
    flag = getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0)
    attrs = getattr(info, "st_file_attributes", 0)
    return bool(flag and attrs & flag)


def _assert_runtime_root(root: Path) -> Path:
    resolved = root.resolve(strict=True)
    if not resolved.is_dir() or _is_reparse_point(root):
        raise ValueError("quarantine root must be a real runtime-owned directory")
    return resolved


def _inspect_suggested_filename(raw: str | None) -> tuple[str, str | None]:
    value = (raw or "download.bin").strip() or "download.bin"
    unsafe = None
    if "/" in value or "\\" in value or ".." in value or re.match(r"^[A-Za-z]:", value):
        unsafe = "SUGGESTED_FILENAME_PATH_TRAVERSAL"
    leaf = value.replace("\\", "/").split("/")[-1]
    leaf = _SAFE_CHARS.sub("_", leaf).strip(" .") or "download.bin"
    stem = leaf.split(".", 1)[0].upper()
    if stem in _WINDOWS_DEVICE_NAMES:
        unsafe = unsafe or "SUGGESTED_FILENAME_DEVICE_NAME"
        leaf = "download.bin"
    return leaf[:255], unsafe


def _mime_extension_mismatch(content_type: str | None, filename: str) -> bool | None:
    if not content_type:
        return None
    declared = content_type.split(";", 1)[0].strip().lower()
    if not declared or declared == "application/octet-stream":
        return None
    guessed, _ = mimetypes.guess_type(filename)
    if guessed is None:
        return None
    return guessed.lower() != declared


def _source_summary(source_url: str) -> tuple[str, str]:
    origin = NormalizedOrigin.parse(source_url).serialize()
    summary = minimize_url(source_url)
    return origin, summary["path_digest"]


class DownloadQuarantine:
    """Runtime-owned hostile-byte quarantine.

    Destination naming is owned by the runtime, the page-suggested filename is
    evidence only, and this primitive never promotes a file.
    """

    def __init__(
        self,
        root: Path,
        limits: DownloadLimits,
        *,
        id_factory: Callable[[], str] | None = None,
        clock: Callable[[], float] = monotonic,
    ) -> None:
        self.root = _assert_runtime_root(root)
        self.limits = limits
        self._id_factory = id_factory or (lambda: uuid4().hex)
        self._clock = clock
        self._deadline = self._clock() + limits.max_elapsed_seconds
        self.downloads_used = 0
        self.aggregate_bytes_used = 0

    def _allocate(self) -> tuple[Path, Path, str]:
        for _ in range(32):
            token = str(self._id_factory())
            if not re.fullmatch(r"[A-Za-z0-9_-]{1,128}", token):
                raise ValueError("download quarantine id is invalid")
            partial = self.root / f"download-{token}.partial"
            final = self.root / f"download-{token}.quarantine"
            if partial.exists() or final.exists():
                continue
            partial.parent.resolve(strict=True).relative_to(self.root)
            return partial, final, final.name
        raise DownloadQuarantineError("unable to allocate collision-free quarantine destination")

    def _record(
        self,
        *,
        state: str,
        source_origin: str,
        source_path_digest: str,
        suggested_filename: str,
        content_type: str | None,
        declared_size: int | None,
        observed_bytes: int,
        digest: str | None,
        quarantine_name: str | None,
        reason: str | None,
    ) -> DownloadRecord:
        return DownloadRecord(
            state=state,
            source_origin=source_origin,
            source_path_digest=source_path_digest,
            suggested_filename=suggested_filename,
            content_type=content_type,
            declared_size=declared_size,
            observed_bytes=observed_bytes,
            sha256=digest,
            quarantine_name=quarantine_name,
            promoted=False,
            mime_extension_mismatch=_mime_extension_mismatch(content_type, suggested_filename),
            reason=reason,
        )

    def quarantine_chunks(
        self,
        chunks: Iterable[bytes],
        *,
        source_url: str,
        suggested_filename: str | None,
        content_type: str | None = None,
        declared_size: int | None = None,
    ) -> DownloadRecord:
        source_origin, source_path_digest = _source_summary(source_url)
        safe_name, unsafe_reason = _inspect_suggested_filename(suggested_filename)
        if unsafe_reason is not None:
            return self._record(
                state="BLOCKED",
                source_origin=source_origin,
                source_path_digest=source_path_digest,
                suggested_filename=safe_name,
                content_type=content_type,
                declared_size=declared_size,
                observed_bytes=0,
                digest=None,
                quarantine_name=None,
                reason=unsafe_reason,
            )

        if declared_size is not None:
            if declared_size < 0:
                raise ValueError("declared download size cannot be negative")
            if declared_size > self.limits.max_file_bytes:
                return self._record(
                    state="BLOCKED",
                    source_origin=source_origin,
                    source_path_digest=source_path_digest,
                    suggested_filename=safe_name,
                    content_type=content_type,
                    declared_size=declared_size,
                    observed_bytes=0,
                    digest=None,
                    quarantine_name=None,
                    reason="DOWNLOAD_FILE_SIZE_BUDGET_EXHAUSTED",
                )
            if self.aggregate_bytes_used + declared_size > self.limits.max_aggregate_bytes:
                return self._record(
                    state="BLOCKED",
                    source_origin=source_origin,
                    source_path_digest=source_path_digest,
                    suggested_filename=safe_name,
                    content_type=content_type,
                    declared_size=declared_size,
                    observed_bytes=0,
                    digest=None,
                    quarantine_name=None,
                    reason="DOWNLOAD_AGGREGATE_SIZE_BUDGET_EXHAUSTED",
                )

        if self._clock() >= self._deadline:
            return self._record(
                state="BLOCKED",
                source_origin=source_origin,
                source_path_digest=source_path_digest,
                suggested_filename=safe_name,
                content_type=content_type,
                declared_size=declared_size,
                observed_bytes=0,
                digest=None,
                quarantine_name=None,
                reason="DOWNLOAD_ELAPSED_BUDGET_EXHAUSTED",
            )

        if self.downloads_used >= self.limits.max_downloads:
            return self._record(
                state="BLOCKED",
                source_origin=source_origin,
                source_path_digest=source_path_digest,
                suggested_filename=safe_name,
                content_type=content_type,
                declared_size=declared_size,
                observed_bytes=0,
                digest=None,
                quarantine_name=None,
                reason="DOWNLOAD_COUNT_BUDGET_EXHAUSTED",
            )

        partial, final, final_name = self._allocate()
        self.downloads_used += 1
        aggregate_before = self.aggregate_bytes_used
        observed = 0
        digest = sha256()
        reason = None
        state = "QUARANTINED"

        try:
            with partial.open("xb") as handle:
                if _is_reparse_point(partial):
                    raise DownloadQuarantineError("quarantine destination became a reparse point")
                for chunk in chunks:
                    if self._clock() >= self._deadline:
                        reason = "DOWNLOAD_ELAPSED_BUDGET_EXHAUSTED"
                        state = "INCOMPLETE"
                        break
                    if not isinstance(chunk, (bytes, bytearray, memoryview)):
                        raise TypeError("download chunks must be bytes")
                    data = bytes(chunk)
                    next_file_size = observed + len(data)
                    next_aggregate = self.aggregate_bytes_used + len(data)
                    if next_file_size > self.limits.max_file_bytes:
                        reason = "DOWNLOAD_FILE_SIZE_BUDGET_EXHAUSTED"
                        state = "INCOMPLETE"
                        break
                    if next_aggregate > self.limits.max_aggregate_bytes:
                        reason = "DOWNLOAD_AGGREGATE_SIZE_BUDGET_EXHAUSTED"
                        state = "INCOMPLETE"
                        break
                    handle.write(data)
                    digest.update(data)
                    observed = next_file_size
                    self.aggregate_bytes_used = next_aggregate
        except DownloadTransferCancelled:
            state = "INCOMPLETE"
            reason = "DOWNLOAD_CANCELLED"
        except Exception:
            state = "INCOMPLETE"
            reason = "DOWNLOAD_TRANSFER_FAILED"

        if state == "QUARANTINED":
            if declared_size is not None and observed != declared_size:
                state = "INCOMPLETE"
                reason = "DOWNLOAD_DECLARED_SIZE_MISMATCH"
            else:
                os.replace(partial, final)
                final.resolve(strict=True).relative_to(self.root)
                return self._record(
                    state="QUARANTINED",
                    source_origin=source_origin,
                    source_path_digest=source_path_digest,
                    suggested_filename=safe_name,
                    content_type=content_type,
                    declared_size=declared_size,
                    observed_bytes=observed,
                    digest="sha256:" + digest.hexdigest(),
                    quarantine_name=final_name,
                    reason=None,
                )

        partial_name = partial.name if partial.exists() else None
        if partial.exists():
            retained = partial.read_bytes()
            observed = len(retained)
            partial_digest = "sha256:" + sha256(retained).hexdigest() if retained else None
            self.aggregate_bytes_used = aggregate_before + observed
        else:
            observed = 0
            partial_digest = None
            self.aggregate_bytes_used = aggregate_before
        return self._record(
            state="INCOMPLETE",
            source_origin=source_origin,
            source_path_digest=source_path_digest,
            suggested_filename=safe_name,
            content_type=content_type,
            declared_size=declared_size,
            observed_bytes=observed,
            digest=partial_digest,
            quarantine_name=partial_name,
            reason=reason,
        )

    def quarantine_file(
        self,
        source_path: Path,
        *,
        source_url: str,
        suggested_filename: str | None,
        content_type: str | None = None,
        declared_size: int | None = None,
        chunk_size: int = 1024 * 1024,
    ) -> DownloadRecord:
        path = source_path.resolve(strict=True)
        if _is_reparse_point(source_path) or not path.is_file():
            raise DownloadQuarantineError("download source must be a regular non-reparse file")
        before = path.stat()

        with path.open("rb") as handle:
            opened_stat = os.fstat(handle.fileno())
            if not stat.S_ISREG(opened_stat.st_mode):
                raise DownloadQuarantineError("download source handle must be a regular file")
            if not os.path.samestat(before, opened_stat):
                raise DownloadQuarantineError("download source changed before it could be opened safely")

            def read_chunks() -> Iterator[bytes]:
                while True:
                    chunk = handle.read(chunk_size)
                    if not chunk:
                        return
                    yield chunk

            result = self.quarantine_chunks(
                read_chunks(),
                source_url=source_url,
                suggested_filename=suggested_filename,
                content_type=content_type,
                declared_size=declared_size,
            )

        after = path.stat()
        if not os.path.samestat(opened_stat, after):
            raise DownloadQuarantineError("download source path changed while being quarantined")
        return result
