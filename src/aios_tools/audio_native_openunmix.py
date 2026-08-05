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
from typing import Any, Iterable

EXPECTED_TARGETS = ("vocals", "drums", "bass", "other")


class NativeOpenUnmixError(RuntimeError):
    def __init__(self, code: str, message: str, *, details: dict[str, Any] | None = None) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.details = details or {}


@dataclass(frozen=True)
class NativeOpenUnmixProfile:
    profile_id: str
    executable: str
    model: str
    targets: tuple[str, ...]
    no_cuda: bool
    niter: int
    wiener_win_len: int
    filterbank: str
    extension: str
    timeout_seconds: int
    source_sha256: str | None = None

    @classmethod
    def from_json(cls, path: Path) -> "NativeOpenUnmixProfile":
        data = json.loads(path.read_text(encoding="utf-8"))
        return cls(
            profile_id=str(data["profile_id"]),
            executable=str(data["executable"]),
            model=str(data["model"]),
            targets=tuple(data["targets"]),
            no_cuda=bool(data["no_cuda"]),
            niter=int(data["niter"]),
            wiener_win_len=int(data["wiener_win_len"]),
            filterbank=str(data["filterbank"]),
            extension=str(data["extension"]),
            timeout_seconds=int(data["timeout_seconds"]),
            source_sha256=data.get("source_sha256"),
        )

    def validate(self) -> None:
        if self.targets != EXPECTED_TARGETS:
            raise NativeOpenUnmixError("PROFILE_INVALID", f"targets must be {EXPECTED_TARGETS}, got {self.targets}")
        if self.model != "umxhq":
            raise NativeOpenUnmixError("PROFILE_INVALID", "model must be umxhq")
        if not self.no_cuda:
            raise NativeOpenUnmixError("PROFILE_INVALID", "CPU reference profile requires no_cuda=true")
        if self.niter < 0 or self.wiener_win_len <= 0 or self.timeout_seconds <= 0:
            raise NativeOpenUnmixError("PROFILE_INVALID", "niter, wiener_win_len, and timeout must be bounded")
        if self.filterbank not in {"torch", "asteroid"}:
            raise NativeOpenUnmixError("PROFILE_INVALID", "unsupported filterbank")
        if self.extension not in {"wav", "flac"}:
            raise NativeOpenUnmixError("PROFILE_INVALID", "unsupported output extension")


def sha256_file(path: Path, *, chunk_size: int = 1024 * 1024) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while True:
            block = handle.read(chunk_size)
            if not block:
                break
            digest.update(block)
    return digest.hexdigest()


def build_command(profile: NativeOpenUnmixProfile, source: Path, outdir: Path) -> list[str]:
    profile.validate()
    command = [
        profile.executable,
        str(source),
        "--model",
        profile.model,
        "--targets",
        *profile.targets,
        "--outdir",
        str(outdir),
        "--ext",
        profile.extension,
        "--niter",
        str(profile.niter),
        "--wiener-win-len",
        str(profile.wiener_win_len),
        "--filterbank",
        profile.filterbank,
        "--verbose",
    ]
    if profile.no_cuda:
        command.append("--no-cuda")
    return command


def _find_stem_files(root: Path, extension: str) -> dict[str, Path]:
    found: dict[str, Path] = {}
    for target in EXPECTED_TARGETS:
        matches = [path for path in root.rglob(f"{target}.{extension}") if path.is_file()]
        if len(matches) != 1:
            raise NativeOpenUnmixError(
                "OUTPUT_SET_INVALID",
                f"expected exactly one {target}.{extension}, found {len(matches)}",
            )
        found[target] = matches[0]
    return found


def _manifest(paths: Iterable[Path], root: Path) -> list[dict[str, Any]]:
    return [
        {
            "relative_path": path.relative_to(root).as_posix(),
            "sha256": sha256_file(path),
            "byte_size": path.stat().st_size,
        }
        for path in sorted(paths)
    ]


def run_native_openunmix(
    *,
    source: Path,
    output_root: Path,
    profile: NativeOpenUnmixProfile,
    env: dict[str, str] | None = None,
) -> dict[str, Any]:
    source = source.resolve(strict=True)
    output_root = output_root.resolve()
    profile.validate()
    executable = shutil.which(profile.executable) if os.sep not in profile.executable else profile.executable
    if not executable or not Path(executable).is_file():
        raise NativeOpenUnmixError("EXECUTABLE_NOT_FOUND", profile.executable)
    source_hash = sha256_file(source)
    if profile.source_sha256 and source_hash != profile.source_sha256:
        raise NativeOpenUnmixError("SOURCE_HASH_MISMATCH", f"expected {profile.source_sha256}, got {source_hash}")
    if output_root.exists():
        raise NativeOpenUnmixError("OUTPUT_ALREADY_EXISTS", str(output_root))
    stage = output_root.with_name(f".{output_root.name}.staging-{os.getpid()}")
    if stage.exists():
        shutil.rmtree(stage)
    stage.mkdir(parents=True)
    command = build_command(profile, source, stage)
    started = time.time()
    stdout_path = stage / "stdout.log"
    stderr_path = stage / "stderr.log"
    completed = False
    try:
        with stdout_path.open("wb") as stdout_handle, stderr_path.open("wb") as stderr_handle:
            process = subprocess.Popen(
                command,
                stdout=stdout_handle,
                stderr=stderr_handle,
                env=env or os.environ.copy(),
                start_new_session=True,
            )
            timed_out = False
            try:
                returncode = process.wait(timeout=profile.timeout_seconds)
            except subprocess.TimeoutExpired:
                timed_out = True
                os.killpg(process.pid, signal.SIGTERM)
                try:
                    process.wait(timeout=10)
                except subprocess.TimeoutExpired:
                    os.killpg(process.pid, signal.SIGKILL)
                    process.wait(timeout=10)
                returncode = process.returncode
        receipt: dict[str, Any] = {
            "schema_version": "0.1.0",
            "status": "TIMED_OUT" if timed_out else ("COMPLETED" if returncode == 0 else "FAILED"),
            "profile_id": profile.profile_id,
            "source": {"path": str(source), "sha256": source_hash, "byte_size": source.stat().st_size},
            "command": command,
            "returncode": returncode,
            "timed_out": timed_out,
            "elapsed_seconds": round(time.time() - started, 6),
            "stdout": "stdout.log",
            "stderr": "stderr.log",
            "runtime_admission": False,
            "pilot_authorized": False,
            "authority_transfer": False,
        }
        if timed_out or returncode != 0:
            receipt["failure_code"] = "NATIVE_PROCESS_TIMEOUT" if timed_out else "NATIVE_PROCESS_FAILED"
            (stage / "run-receipt.json").write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n", encoding="utf-8")
            failure_root = output_root.with_name(f"{output_root.name}.failed")
            if failure_root.exists():
                shutil.rmtree(failure_root)
            os.replace(stage, failure_root)
            completed = True
            return receipt | {"evidence_root": str(failure_root)}
        stems = _find_stem_files(stage, profile.extension)
        receipt["stems"] = {
            name: {
                "relative_path": path.relative_to(stage).as_posix(),
                "sha256": sha256_file(path),
                "byte_size": path.stat().st_size,
                "evidence_class": "MODEL_ESTIMATE",
            }
            for name, path in stems.items()
        }
        receipt["artifact_manifest"] = _manifest([*stems.values(), stdout_path, stderr_path], stage)
        (stage / "run-receipt.json").write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        os.replace(stage, output_root)
        completed = True
        return receipt | {"evidence_root": str(output_root)}
    finally:
        if not completed and stage.exists():
            shutil.rmtree(stage, ignore_errors=True)
