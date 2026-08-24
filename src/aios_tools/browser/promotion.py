from __future__ import annotations

from dataclasses import asdict, dataclass
from hashlib import sha256
import json
import os
from pathlib import Path
import re
import shutil
import stat
from uuid import uuid4

from .downloads import DownloadRecord, _is_reparse_point


_QUARANTINE_NAME_RE = re.compile(r"^download-[A-Za-z0-9_-]{1,128}\.quarantine$")
_EXECUTABLE_EXTENSIONS = frozenset({
    ".exe", ".com", ".bat", ".cmd", ".ps1", ".msi", ".scr", ".dll", ".jar", ".app", ".sh"
})


class DownloadPromotionError(RuntimeError):
    pass


@dataclass(frozen=True, slots=True)
class DownloadPromotionRules:
    profile_id: str
    auto_promote: bool
    allowed_content_types: tuple[str, ...]
    allowed_extensions: tuple[str, ...]
    max_bytes: int

    def __post_init__(self) -> None:
        if not self.profile_id or any(ch.isspace() for ch in self.profile_id):
            raise ValueError("promotion profile_id must be compact")
        if self.max_bytes < 1:
            raise ValueError("promotion max_bytes must be positive")
        if not self.allowed_content_types or not self.allowed_extensions:
            raise ValueError("promotion rules require declared content types and extensions")


@dataclass(frozen=True, slots=True)
class PromotionReceipt:
    artifact_ref: str
    profile_id: str
    sha256: str
    observed_bytes: int
    content_type: str
    display_name: str
    relative_path: str
    automatic: bool
    source_quarantine_deleted: bool
    authority_transfer: bool = False

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


def _safe_leaf(value: str) -> str:
    leaf = value.replace("\\", "/").split("/")[-1]
    leaf = re.sub(r"[^A-Za-z0-9._ -]+", "_", leaf).strip(" .")
    if not leaf or leaf in {".", ".."}:
        raise DownloadPromotionError("download display name is invalid")
    return leaf[:255]


def _rehash(path: Path) -> tuple[str, int]:
    digest = sha256()
    total = 0
    with path.open("rb") as handle:
        while True:
            chunk = handle.read(1024 * 1024)
            if not chunk:
                break
            total += len(chunk)
            digest.update(chunk)
    return "sha256:" + digest.hexdigest(), total


class DownloadPromotionManager:
    def __init__(self, *, quarantine_root: Path, artifact_root: Path, manifest_path: Path) -> None:
        if (
            _is_reparse_point(quarantine_root)
            or _is_reparse_point(artifact_root)
            or _is_reparse_point(manifest_path)
        ):
            raise DownloadPromotionError("promotion runtime roots may not be symlinks or reparse points")
        self.quarantine_root = quarantine_root.resolve(strict=True)
        self.artifact_root = artifact_root.resolve(strict=True)
        self.manifest_path = manifest_path.resolve(strict=True)
        if not self.quarantine_root.is_dir() or not self.artifact_root.is_dir() or not self.manifest_path.is_file():
            raise DownloadPromotionError("promotion runtime roots are unavailable")

    @classmethod
    def from_environment(cls) -> "DownloadPromotionManager":
        q = os.environ.get("AIOS_BROWSER_QUARANTINE_ROOT")
        a = os.environ.get("AIOS_ARTIFACT_ROOT")
        m = os.environ.get("AIOS_ARTIFACT_MANIFEST")
        if not q or not a or not m:
            raise DownloadPromotionError("download promotion runtime is not configured")
        return cls(
            quarantine_root=Path(q).expanduser(),
            artifact_root=Path(a).expanduser(),
            manifest_path=Path(m).expanduser(),
        )

    def promote(self, record: DownloadRecord, rules: DownloadPromotionRules) -> PromotionReceipt:
        if rules.auto_promote is not True:
            raise DownloadPromotionError("profile does not admit automatic promotion")
        if record.state != "QUARANTINED" or record.promoted or not record.sha256 or not record.quarantine_name:
            raise DownloadPromotionError("only complete quarantined downloads may be promoted")
        if not _QUARANTINE_NAME_RE.fullmatch(record.quarantine_name):
            raise DownloadPromotionError("quarantine entry name is not runtime-owned")
        if record.mime_extension_mismatch is True:
            raise DownloadPromotionError("MIME/extension mismatch blocks promotion")
        if not isinstance(record.content_type, str) or record.content_type not in rules.allowed_content_types:
            raise DownloadPromotionError("download content type is not admitted")
        if record.observed_bytes < 0 or record.observed_bytes > rules.max_bytes:
            raise DownloadPromotionError("download size is not admitted")

        display_name = _safe_leaf(record.suggested_filename)
        extension = Path(display_name).suffix.lower()
        if extension in _EXECUTABLE_EXTENSIONS:
            raise DownloadPromotionError("executable download class is blocked")
        if extension not in {item.lower() for item in rules.allowed_extensions}:
            raise DownloadPromotionError("download extension is not admitted")

        source_entry = self.quarantine_root / record.quarantine_name
        if _is_reparse_point(source_entry):
            raise DownloadPromotionError("quarantine source may not be a symlink or reparse point")
        source = source_entry.resolve(strict=True)
        source.relative_to(self.quarantine_root)
        if not source.is_file():
            raise DownloadPromotionError("quarantine source is not a regular file")
        before = source.stat()

        token = uuid4().hex
        relative = Path("browser-downloads") / f"{token}-{display_name}"
        target = self.artifact_root / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        digest = sha256()
        observed_bytes = 0
        try:
            with source.open("rb") as src, target.open("xb") as dst:
                opened = os.fstat(src.fileno())
                if not stat.S_ISREG(opened.st_mode) or not os.path.samestat(before, opened):
                    raise DownloadPromotionError("quarantine source changed before promotion")
                while True:
                    chunk = src.read(1024 * 1024)
                    if not chunk:
                        break
                    observed_bytes += len(chunk)
                    if observed_bytes > rules.max_bytes:
                        raise DownloadPromotionError("download size changed beyond promotion budget")
                    digest.update(chunk)
                    dst.write(chunk)
                dst.flush()
                os.fsync(dst.fileno())
            after = source.stat()
            if (
                not os.path.samestat(opened, after)
                or getattr(before, "st_mtime_ns", None) != getattr(after, "st_mtime_ns", None)
                or before.st_size != after.st_size
            ):
                raise DownloadPromotionError("quarantine source changed during promotion")
            observed_hash = "sha256:" + digest.hexdigest()
            if observed_hash != record.sha256 or observed_bytes != record.observed_bytes:
                raise DownloadPromotionError("quarantine evidence changed before promotion")
            target_hash, target_bytes = _rehash(target)
            if target_hash != observed_hash or target_bytes != observed_bytes:
                raise DownloadPromotionError("promoted artifact verification failed")
        except Exception:
            target.unlink(missing_ok=True)
            raise

        artifact_ref = f"artifact:browser-download:{token}"
        lock_path = self.manifest_path.with_name(self.manifest_path.name + ".lock")
        lock_fd: int | None = None
        try:
            try:
                lock_fd = os.open(lock_path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
                os.write(lock_fd, f"{os.getpid()}\n".encode("ascii"))
                os.fsync(lock_fd)
            except FileExistsError as exc:
                target.unlink(missing_ok=True)
                raise DownloadPromotionError("artifact manifest is locked by another promotion") from exc

            try:
                manifest = json.loads(self.manifest_path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError) as exc:
                target.unlink(missing_ok=True)
                raise DownloadPromotionError("artifact manifest is invalid") from exc
            if not isinstance(manifest, dict) or not isinstance(manifest.get("artifacts"), dict):
                target.unlink(missing_ok=True)
                raise DownloadPromotionError("artifact manifest is invalid")
            if artifact_ref in manifest["artifacts"]:
                target.unlink(missing_ok=True)
                raise DownloadPromotionError("artifact reference collision")
            manifest["artifacts"][artifact_ref] = {
                "path": relative.as_posix(),
                "sha256": target_hash,
                "media_type": record.content_type,
                "display_name": display_name,
                "source_profile_id": rules.profile_id,
            }
            temp = self.manifest_path.with_name(self.manifest_path.name + f".{token}.tmp")
            temp.write_text(json.dumps(manifest, sort_keys=True, indent=2) + "\n", encoding="utf-8")
            with temp.open("rb") as manifest_handle:
                os.fsync(manifest_handle.fileno())
            os.replace(temp, self.manifest_path)
        finally:
            if lock_fd is not None:
                os.close(lock_fd)
                try:
                    lock_path.unlink()
                except FileNotFoundError:
                    pass
        return PromotionReceipt(
            artifact_ref=artifact_ref,
            profile_id=rules.profile_id,
            sha256=target_hash,
            observed_bytes=target_bytes,
            content_type=record.content_type,
            display_name=display_name,
            relative_path=relative.as_posix(),
            automatic=True,
            source_quarantine_deleted=False,
            authority_transfer=False,
        )
