from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
import mimetypes
import os
from pathlib import Path
import re
import stat
from typing import Mapping, Protocol


class ArtifactResolutionError(RuntimeError):
    pass


class UploadPreparationError(RuntimeError):
    pass


_ARTIFACT_REF_RE = re.compile(r"^artifact:[A-Za-z0-9][A-Za-z0-9_.-]{0,63}:[A-Za-z0-9][A-Za-z0-9_.-]{0,127}$")


@dataclass(frozen=True, slots=True)
class ArtifactRef:
    value: str

    def __post_init__(self) -> None:
        if not _ARTIFACT_REF_RE.fullmatch(self.value):
            raise ValueError("invalid governed artifact reference")


@dataclass(frozen=True, slots=True)
class ArtifactDescriptor:
    ref: ArtifactRef
    runtime_path: Path
    expected_sha256: str | None
    media_type: str | None = None
    display_name: str | None = None


class GovernedArtifactResolver(Protocol):
    def resolve(self, ref: ArtifactRef) -> ArtifactDescriptor:
        ...


@dataclass(frozen=True, slots=True)
class UploadLimits:
    max_file_bytes: int

    def __post_init__(self) -> None:
        if self.max_file_bytes < 1:
            raise ValueError("upload max_file_bytes must be positive")


@dataclass(frozen=True, slots=True)
class UploadReceipt:
    artifact_ref: str
    observed_bytes: int
    sha256: str
    media_type: str
    filename: str
    regular_file: bool
    promoted: bool
    remote_submission_authorized: bool
    authority_transfer: bool

    def to_dict(self) -> dict:
        return {
            "artifact_ref": self.artifact_ref,
            "observed_bytes": self.observed_bytes,
            "sha256": self.sha256,
            "media_type": self.media_type,
            "filename": self.filename,
            "regular_file": self.regular_file,
            "promoted": self.promoted,
            "remote_submission_authorized": self.remote_submission_authorized,
            "authority_transfer": self.authority_transfer,
        }


@dataclass(frozen=True, slots=True)
class PreparedUpload:
    """Internal browser payload. Bytes are intentionally excluded from receipts."""

    artifact_ref: ArtifactRef
    filename: str
    media_type: str
    buffer: bytes
    receipt: UploadReceipt

    def playwright_file_payload(self) -> dict[str, object]:
        return {
            "name": self.filename,
            "mimeType": self.media_type,
            "buffer": self.buffer,
        }


class UnavailableArtifactResolver:
    def resolve(self, ref: ArtifactRef) -> ArtifactDescriptor:
        raise ArtifactResolutionError("governed artifact resolver is unavailable")


class SyntheticArtifactResolver:
    """CI-only resolver. Production registration is intentionally absent."""

    def __init__(self, records: Mapping[str, ArtifactDescriptor]) -> None:
        self._records = dict(records)

    def resolve(self, ref: ArtifactRef) -> ArtifactDescriptor:
        try:
            descriptor = self._records[ref.value]
        except KeyError as exc:
            raise ArtifactResolutionError("governed artifact reference was not found") from exc
        if descriptor.ref != ref:
            raise ArtifactResolutionError("artifact resolver returned mismatched reference")
        return descriptor


def _is_reparse_point(path: Path) -> bool:
    info = path.lstat()
    if stat.S_ISLNK(info.st_mode):
        return True
    flag = getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0)
    attrs = getattr(info, "st_file_attributes", 0)
    return bool(flag and attrs & flag)


def _safe_filename(value: str | None, fallback: str) -> str:
    raw = (value or fallback).strip()
    leaf = raw.replace("\\", "/").split("/")[-1]
    leaf = re.sub(r"[^A-Za-z0-9._ -]+", "_", leaf).strip(" .")
    if not leaf or leaf in {".", ".."}:
        return "artifact.bin"
    return leaf[:255]


class UploadIntake:
    """Resolve one governed artifact ref into a bounded in-memory browser payload.

    This layer does not submit a form, navigate, click, or grant remote mutation.
    """

    def __init__(
        self,
        resolver: GovernedArtifactResolver,
        *,
        artifact_root: Path,
        limits: UploadLimits,
    ) -> None:
        self.resolver = resolver
        self.artifact_root = artifact_root.resolve(strict=True)
        if not self.artifact_root.is_dir() or _is_reparse_point(artifact_root):
            raise ValueError("artifact root must be a real governed directory")
        self.limits = limits

    def prepare(self, artifact_ref: str) -> PreparedUpload:
        ref = ArtifactRef(artifact_ref)
        descriptor = self.resolver.resolve(ref)

        original = descriptor.runtime_path
        if _is_reparse_point(original):
            raise UploadPreparationError("artifact path may not be a symlink or reparse point")
        resolved = original.resolve(strict=True)
        try:
            resolved.relative_to(self.artifact_root)
        except ValueError as exc:
            raise UploadPreparationError("artifact path escaped governed artifact root") from exc
        if not resolved.is_file():
            raise UploadPreparationError("artifact must resolve to a regular file")

        before = resolved.stat()
        if before.st_size > self.limits.max_file_bytes:
            raise UploadPreparationError("artifact exceeds upload size budget")

        digest = sha256()
        data = bytearray()
        with resolved.open("rb") as handle:
            opened = handle.fileno()
            opened_stat = os.fstat(opened)
            if not stat.S_ISREG(opened_stat.st_mode):
                raise UploadPreparationError("artifact handle is not a regular file")
            if not os.path.samestat(before, opened_stat):
                raise UploadPreparationError("artifact changed before it could be opened safely")
            while True:
                chunk = handle.read(min(1024 * 1024, self.limits.max_file_bytes + 1 - len(data)))
                if not chunk:
                    break
                data.extend(chunk)
                if len(data) > self.limits.max_file_bytes:
                    raise UploadPreparationError("artifact exceeds upload size budget")
                digest.update(chunk)

        after = resolved.stat()
        if (
            not os.path.samestat(opened_stat, after)
            or before.st_size != after.st_size
            or getattr(before, "st_mtime_ns", None) != getattr(after, "st_mtime_ns", None)
            or getattr(opened_stat, "st_size", before.st_size) != len(data)
        ):
            raise UploadPreparationError("artifact changed while being prepared")

        observed_digest = "sha256:" + digest.hexdigest()
        if descriptor.expected_sha256 is not None and descriptor.expected_sha256 != observed_digest:
            raise UploadPreparationError("artifact hash mismatch")

        filename = _safe_filename(descriptor.display_name, resolved.name)
        media_type = descriptor.media_type or mimetypes.guess_type(filename)[0] or "application/octet-stream"
        receipt = UploadReceipt(
            artifact_ref=ref.value,
            observed_bytes=len(data),
            sha256=observed_digest,
            media_type=media_type,
            filename=filename,
            regular_file=True,
            promoted=False,
            remote_submission_authorized=False,
            authority_transfer=False,
        )
        return PreparedUpload(
            artifact_ref=ref,
            filename=filename,
            media_type=media_type,
            buffer=bytes(data),
            receipt=receipt,
        )
