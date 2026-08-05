from __future__ import annotations

import hashlib
import json
import os
import shutil
import signal
import subprocess
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

EXPECTED_STEMS = ("drums", "bass", "other", "vocals")


class NativeDemucsError(RuntimeError):
    def __init__(self, code: str, message: str, *, details: dict[str, Any] | None = None) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.details = details or {}


@dataclass(frozen=True)
class NativeDemucsProfile:
    profile_id: str
    entrypoint: tuple[str, ...]
    model: str
    device: str
    jobs: int
    split: bool
    segment_seconds: float
    overlap: float
    shifts: int
    output_format: str
    float32: bool
    timeout_seconds: int
    source_sha256: str | None = None

    @classmethod
    def from_json(cls, path: Path) -> "NativeDemucsProfile":
        data = json.loads(path.read_text(encoding="utf-8"))
        return cls(
            profile_id=str(data["profile_id"]),
            entrypoint=tuple(data["entrypoint"]),
            model=str(data["model"]),
            device=str(data["device"]),
            jobs=int(data["jobs"]),
            split=bool(data["split"]),
            segment_seconds=float(data["segment_seconds"]),
            overlap=float(data["overlap"]),
            shifts=int(data["shifts"]),
            output_format=str(data["output_format"]),
            float32=bool(data["float32"]),
            timeout_seconds=int(data["timeout_seconds"]),
            source_sha256=data.get("source_sha256"),
        )

    def validate(self) -> None:
        if self.model != "htdemucs":
            raise NativeDemucsError("PROFILE_INVALID", "model must be htdemucs")
        if self.device != "cpu" or self.jobs != 1:
            raise NativeDemucsError("PROFILE_INVALID", "reference profile requires cpu and jobs=1")
        if not self.split:
            raise NativeDemucsError("PROFILE_INVALID", "upstream split mode must remain enabled")
        if not (0 < self.segment_seconds <= 7.8):
            raise NativeDemucsError("PROFILE_INVALID", "segment_seconds must be in (0, 7.8]")
        if not (0 <= self.overlap < 1):
            raise NativeDemucsError("PROFILE_INVALID", "overlap must be in [0,1)")
        if self.shifts != 0:
            raise NativeDemucsError("PROFILE_INVALID", "reference profile freezes shifts=0")
        if self.output_format != "wav" or not self.float32:
            raise NativeDemucsError("PROFILE_INVALID", "reference profile requires float32 WAV")
        if self.timeout_seconds <= 0:
            raise NativeDemucsError("PROFILE_INVALID", "timeout must be positive")


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def build_command(profile: NativeDemucsProfile, source: Path, output_root: Path) -> list[str]:
    profile.validate()
    command = [
        *profile.entrypoint,
        "--name", profile.model,
        "--device", profile.device,
        "--jobs", str(profile.jobs),
        "--segment", str(profile.segment_seconds),
        "--overlap", str(profile.overlap),
        "--shifts", str(profile.shifts),
        "--out", str(output_root),
        "--filename", "{stem}.{ext}",
    ]
    if profile.float32:
        command.append("--float32")
    command.append(str(source))
    return command


def _find_outputs(root: Path) -> dict[str, Path]:
    found: dict[str, Path] = {}
    for stem in EXPECTED_STEMS:
        matches = [path for path in root.rglob(f"{stem}.wav") if path.is_file()]
        if len(matches) != 1:
            raise NativeDemucsError("OUTPUT_SET_INVALID", f"expected one {stem}.wav, found {len(matches)}")
        found[stem] = matches[0]
    return found


def run_native_demucs(profile: NativeDemucsProfile, source: Path, output_dir: Path) -> dict[str, Any]:
    profile.validate()
    source = source.resolve(strict=True)
    output_dir = output_dir.resolve()
    if profile.source_sha256 and sha256_file(source) != profile.source_sha256:
        raise NativeDemucsError("SOURCE_HASH_MISMATCH", "source SHA-256 does not match frozen profile")
    executable = shutil.which(profile.entrypoint[0])
    if executable is None:
        raise NativeDemucsError("EXECUTABLE_NOT_FOUND", profile.entrypoint[0])
    if output_dir.exists():
        raise NativeDemucsError("OUTPUT_EXISTS", str(output_dir))

    stage = output_dir.with_name(f".{output_dir.name}.stage")
    if stage.exists():
        shutil.rmtree(stage)
    stage.mkdir(parents=True)
    command = build_command(profile, source, stage)
    started = time.monotonic()
    proc = subprocess.Popen(
        command,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        start_new_session=True,
        env={**os.environ, "HF_HUB_OFFLINE": "1", "TRANSFORMERS_OFFLINE": "1"},
    )
    try:
        stdout, stderr = proc.communicate(timeout=profile.timeout_seconds)
    except subprocess.TimeoutExpired:
        os.killpg(proc.pid, signal.SIGTERM)
        try:
            stdout, stderr = proc.communicate(timeout=10)
        except subprocess.TimeoutExpired:
            os.killpg(proc.pid, signal.SIGKILL)
            stdout, stderr = proc.communicate()
        raise NativeDemucsError(
            "NATIVE_PROCESS_TIMEOUT",
            "Demucs exceeded the frozen timeout",
            details={"stdout": stdout, "stderr": stderr, "elapsed_seconds": time.monotonic() - started},
        )

    elapsed = time.monotonic() - started
    if proc.returncode != 0:
        raise NativeDemucsError(
            "NATIVE_PROCESS_FAILED",
            f"Demucs exited with {proc.returncode}",
            details={"stdout": stdout, "stderr": stderr, "elapsed_seconds": elapsed},
        )
    outputs = _find_outputs(stage)
    manifest = {
        stem: {"path": str(path.relative_to(stage)), "sha256": sha256_file(path), "bytes": path.stat().st_size}
        for stem, path in outputs.items()
    }
    stage.replace(output_dir)
    return {
        "status": "COMPLETE",
        "command": command,
        "elapsed_seconds": elapsed,
        "stdout": stdout,
        "stderr": stderr,
        "artifacts": manifest,
    }
