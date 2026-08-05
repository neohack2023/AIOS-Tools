from __future__ import annotations

import hashlib
import json
import os
import shutil
import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterable


class AudioTransactionError(RuntimeError):
    """Fail-closed error raised by the bounded audio artifact transaction."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message


def _sha256_file(path: Path) -> tuple[str, int]:
    digest = hashlib.sha256()
    size = 0
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            size += len(chunk)
            digest.update(chunk)
    return digest.hexdigest(), size


def _reject_symlink_components(path: Path, label: str, *, include_leaf: bool = True) -> None:
    current = Path(path.anchor)
    parts = path.parts[1:] if path.anchor else path.parts
    for index, part in enumerate(parts):
        current = current / part
        if not include_leaf and index == len(parts) - 1:
            break
        if current.exists() and current.is_symlink():
            raise AudioTransactionError("PATH_BOUNDARY_VIOLATION", f"{label} contains symlink component: {current}")


def _safe_relative_path(value: str) -> Path:
    relative = Path(value)
    if relative.is_absolute() or not relative.parts:
        raise AudioTransactionError("PATH_BOUNDARY_VIOLATION", f"artifact path must be relative: {value}")
    if any(part in {"", ".", ".."} for part in relative.parts):
        raise AudioTransactionError("PATH_BOUNDARY_VIOLATION", f"artifact path contains unsafe component: {value}")
    return relative


@dataclass(frozen=True)
class ArtifactSpec:
    relative_path: str
    media_type: str
    evidence_class: str
    required: bool = True

    def path(self) -> Path:
        return _safe_relative_path(self.relative_path)


@dataclass
class AudioArtifactTransaction:
    output_directory: Path
    run_id: str
    tool_identity: str = "audio.stem_section_analyze"
    profile_id: str = "slice2-stem-section-v0.1"
    profile_checksum: str = "26ac1b86891a8dd7775a3b25bdb7f4b00d9ab284c7575815ce43c5f14e19680f"
    authority_transfer: bool = False
    _staging_directory: Path | None = field(default=None, init=False, repr=False)
    _state: str = field(default="NEW", init=False)

    def prepare(self) -> Path:
        if self.authority_transfer is not False:
            raise AudioTransactionError("AUTHORITY_TRANSFER_BLOCKED", "authority_transfer must remain false")
        if self._state != "NEW":
            raise AudioTransactionError("TRANSACTION_STATE_INVALID", f"cannot prepare from {self._state}")
        output = self.output_directory
        if not output.is_absolute():
            raise AudioTransactionError("PATH_BOUNDARY_VIOLATION", "output directory must be absolute")
        _reject_symlink_components(output, "output_directory", include_leaf=False)
        parent = output.parent
        if not parent.is_dir():
            raise AudioTransactionError("OUTPUT_PARENT_MISSING", f"output parent does not exist: {parent}")
        if output.exists():
            raise AudioTransactionError("OVERWRITE_PROHIBITED", f"output already exists: {output}")
        resolved_parent = parent.resolve(strict=True)
        self.output_directory = resolved_parent / output.name
        staging = Path(tempfile.mkdtemp(prefix=f".{output.name}.{self.run_id}.", dir=resolved_parent))
        _reject_symlink_components(staging, "staging_directory")
        self._staging_directory = staging
        self._state = "PREPARED"
        return staging

    @property
    def staging_directory(self) -> Path:
        if self._staging_directory is None:
            raise AudioTransactionError("TRANSACTION_NOT_PREPARED", "transaction has no staging directory")
        return self._staging_directory

    @property
    def state(self) -> str:
        return self._state

    def artifact_path(self, relative_path: str) -> Path:
        if self._state not in {"PREPARED", "FROZEN"}:
            raise AudioTransactionError("TRANSACTION_STATE_INVALID", f"cannot allocate artifact from {self._state}")
        relative = _safe_relative_path(relative_path)
        candidate = self.staging_directory / relative
        candidate.parent.mkdir(parents=True, exist_ok=True)
        _reject_symlink_components(candidate, "artifact_path", include_leaf=False)
        resolved_parent = candidate.parent.resolve(strict=True)
        try:
            resolved_parent.relative_to(self.staging_directory.resolve(strict=True))
        except ValueError as exc:
            raise AudioTransactionError("PATH_BOUNDARY_VIOLATION", f"artifact escapes staging directory: {relative_path}") from exc
        return resolved_parent / candidate.name

    def build_manifest(self, specs: Iterable[ArtifactSpec]) -> dict[str, Any]:
        if self._state != "PREPARED":
            raise AudioTransactionError("TRANSACTION_STATE_INVALID", f"cannot freeze manifest from {self._state}")
        artifacts: list[dict[str, Any]] = []
        seen: set[str] = set()
        for spec in specs:
            relative = spec.path()
            key = relative.as_posix()
            if key in seen:
                raise AudioTransactionError("INCOMPLETE_ARTIFACT_SET", f"duplicate artifact declaration: {key}")
            seen.add(key)
            path = self.staging_directory / relative
            if not path.is_file():
                if spec.required:
                    raise AudioTransactionError("INCOMPLETE_ARTIFACT_SET", f"required artifact missing: {key}")
                continue
            _reject_symlink_components(path, "artifact")
            sha256, byte_size = _sha256_file(path)
            if byte_size <= 0:
                raise AudioTransactionError("INCOMPLETE_ARTIFACT_SET", f"artifact is empty: {key}")
            artifacts.append(
                {
                    "relative_path": key,
                    "sha256": sha256,
                    "byte_size": byte_size,
                    "media_type": spec.media_type,
                    "evidence_class": spec.evidence_class,
                    "required": spec.required,
                }
            )
        manifest = {
            "schema_version": "0.1.0",
            "run_id": self.run_id,
            "tool_identity": self.tool_identity,
            "profile_id": self.profile_id,
            "profile_checksum": self.profile_checksum,
            "output_root": str(self.output_directory),
            "transaction_state": "FROZEN",
            "artifacts": artifacts,
            "complete": True,
            "authority_transfer": False,
        }
        manifest_path = self.artifact_path("artifact-manifest.json")
        manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        self._state = "FROZEN"
        return manifest

    def promote(self) -> Path:
        if self._state != "FROZEN":
            raise AudioTransactionError("TRANSACTION_STATE_INVALID", f"cannot promote from {self._state}")
        if self.output_directory.exists():
            raise AudioTransactionError("OVERWRITE_PROHIBITED", f"output appeared before promotion: {self.output_directory}")
        staging = self.staging_directory
        try:
            os.replace(staging, self.output_directory)
        except OSError as exc:
            raise AudioTransactionError("PROMOTION_FAILED", f"atomic promotion failed: {exc}") from exc
        self._staging_directory = None
        self._state = "PROMOTED"
        return self.output_directory

    def rollback(self) -> None:
        if self._state == "PROMOTED":
            raise AudioTransactionError("ROLLBACK_FAILED", "promoted output cannot be rolled back by the staging transaction")
        staging = self._staging_directory
        if staging is not None and staging.exists():
            try:
                shutil.rmtree(staging)
            except OSError as exc:
                raise AudioTransactionError("ROLLBACK_FAILED", f"failed to remove staging directory: {exc}") from exc
        self._staging_directory = None
        self._state = "ROLLED_BACK"

    def __enter__(self) -> "AudioArtifactTransaction":
        self.prepare()
        return self

    def __exit__(self, exc_type, exc, traceback) -> bool:
        if exc is not None and self._state != "PROMOTED":
            self.rollback()
        return False
