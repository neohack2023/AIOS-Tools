#!/usr/bin/env python3
"""Governed dependency lock and CPU reference benchmark for Slice 2A.

Network access is allowed only by the ``fetch`` subcommand. The ``benchmark``
and ``review-runtime`` subcommands are offline and fail closed.
"""

from __future__ import annotations

import argparse
import hashlib
import importlib.metadata
import json
import math
import os
import platform
import re
import shutil
import struct
import sys
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

PROFILE_ID = "slice2-stem-section-v0.1"
TOOL_IDENTITY = "audio.stem_section_analyze"
PYPI_JSON_URL = "https://pypi.org/pypi/openunmix/1.3.0/json"
ZENODO_RECORD_URL = "https://zenodo.org/api/records/3370489"
PACKAGE_FILENAME = "openunmix-1.3.0-py3-none-any.whl"
EXPECTED_TARGETS = ["vocals", "drums", "bass", "other"]
ALLOWED_FETCH_HOSTS = frozenset({"pypi.org", "files.pythonhosted.org", "zenodo.org", "www.zenodo.org"})
HEX32 = re.compile(r"^[0-9a-f]{32}$")
HEX64 = re.compile(r"^[0-9a-f]{64}$")
USER_AGENT = "AIOS-Tools-Slice2A-DependencyLock/0.1"


class DependencyLockError(RuntimeError):
    """Raised when any governed dependency or profile check fails closed."""


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def load_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise DependencyLockError(f"JSON file not found: {path}") from exc
    except json.JSONDecodeError as exc:
        raise DependencyLockError(f"invalid JSON in {path}: {exc}") from exc
    if not isinstance(value, dict):
        raise DependencyLockError(f"JSON root must be an object: {path}")
    return value


def write_json(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def canonical_json_bytes(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


def canonical_sha256(value: Any) -> str:
    return hashlib.sha256(canonical_json_bytes(value)).hexdigest()


def hash_file(path: Path) -> dict[str, Any]:
    md5 = hashlib.md5(usedforsecurity=False)
    sha256 = hashlib.sha256()
    size = 0
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            size += len(chunk)
            md5.update(chunk)
            sha256.update(chunk)
    return {"md5": md5.hexdigest(), "sha256": sha256.hexdigest(), "byte_size": size}


def directory_size(path: Path) -> int:
    total = 0
    if not path.exists():
        return 0
    for item in path.rglob("*"):
        if item.is_file():
            total += item.stat().st_size
    return total


def assert_allowed_url(url: str) -> None:
    parsed = urllib.parse.urlparse(url)
    if parsed.scheme != "https":
        raise DependencyLockError(f"only HTTPS fetches are allowed: {url}")
    host = (parsed.hostname or "").lower()
    if host not in ALLOWED_FETCH_HOSTS:
        raise DependencyLockError(f"fetch host is not allowlisted: {host or '<missing>'}")


class RecordingRedirectHandler(urllib.request.HTTPRedirectHandler):
    def __init__(self, redirects: list[str]):
        super().__init__()
        self.redirects = redirects

    def redirect_request(self, req, fp, code, msg, headers, newurl):  # type: ignore[override]
        assert_allowed_url(newurl)
        self.redirects.append(newurl)
        return super().redirect_request(req, fp, code, msg, headers, newurl)


def _open_url(url: str, timeout_seconds: int = 60):
    assert_allowed_url(url)
    redirects: list[str] = []
    handler = RecordingRedirectHandler(redirects)
    opener = urllib.request.build_opener(handler)
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT, "Accept": "*/*"})
    try:
        response = opener.open(request, timeout=timeout_seconds)
    except (urllib.error.URLError, TimeoutError) as exc:
        raise DependencyLockError(f"fetch failed for {url}: {exc}") from exc
    final_url = response.geturl()
    assert_allowed_url(final_url)
    return response, [url, *redirects] if redirects else [url], final_url


def fetch_json(url: str) -> tuple[dict[str, Any], dict[str, Any]]:
    response, chain, final_url = _open_url(url)
    with response:
        payload = response.read()
    try:
        data = json.loads(payload.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise DependencyLockError(f"invalid JSON fetched from {url}: {exc}") from exc
    if not isinstance(data, dict):
        raise DependencyLockError(f"fetched JSON root must be an object: {url}")
    return data, {
        "original_url": url,
        "final_url": final_url,
        "redirect_chain": chain,
        "byte_size": len(payload),
        "sha256": hashlib.sha256(payload).hexdigest(),
    }


def fetch_file(
    url: str,
    destination: Path,
    *,
    expected_sha256: str | None = None,
    expected_md5: str | None = None,
    expected_size: int | None = None,
) -> dict[str, Any]:
    if expected_sha256 is not None and not HEX64.fullmatch(expected_sha256):
        raise DependencyLockError(f"invalid expected SHA-256 for {destination.name}")
    if expected_md5 is not None and not HEX32.fullmatch(expected_md5):
        raise DependencyLockError(f"invalid expected MD5 for {destination.name}")
    destination.parent.mkdir(parents=True, exist_ok=True)
    partial = destination.with_name(destination.name + ".part")
    if partial.exists():
        partial.unlink()
    if destination.exists():
        existing = hash_file(destination)
        if expected_sha256 and existing["sha256"] != expected_sha256:
            raise DependencyLockError(f"existing file SHA-256 mismatch: {destination}")
        if expected_md5 and existing["md5"] != expected_md5:
            raise DependencyLockError(f"existing file MD5 mismatch: {destination}")
        if expected_size is not None and existing["byte_size"] != expected_size:
            raise DependencyLockError(f"existing file byte-size mismatch: {destination}")
        return {
            **existing,
            "original_url": url,
            "final_url": url,
            "redirect_chain": [url],
            "reused_existing": True,
        }

    response, chain, final_url = _open_url(url, timeout_seconds=120)
    md5 = hashlib.md5(usedforsecurity=False)
    sha256 = hashlib.sha256()
    size = 0
    try:
        with response, partial.open("wb") as handle:
            while True:
                chunk = response.read(1024 * 1024)
                if not chunk:
                    break
                handle.write(chunk)
                md5.update(chunk)
                sha256.update(chunk)
                size += len(chunk)
        actual_md5 = md5.hexdigest()
        actual_sha256 = sha256.hexdigest()
        if expected_sha256 and actual_sha256 != expected_sha256:
            raise DependencyLockError(
                f"SHA-256 mismatch for {destination.name}: expected {expected_sha256}, got {actual_sha256}"
            )
        if expected_md5 and actual_md5 != expected_md5:
            raise DependencyLockError(
                f"MD5 mismatch for {destination.name}: expected {expected_md5}, got {actual_md5}"
            )
        if expected_size is not None and size != expected_size:
            raise DependencyLockError(
                f"byte-size mismatch for {destination.name}: expected {expected_size}, got {size}"
            )
        partial.replace(destination)
    except Exception:
        partial.unlink(missing_ok=True)
        raise
    return {
        "md5": actual_md5,
        "sha256": actual_sha256,
        "byte_size": size,
        "original_url": url,
        "final_url": final_url,
        "redirect_chain": chain,
        "reused_existing": False,
    }



def write_float32_wav(path: Path, audio: Any, sample_rate: int) -> None:
    import numpy as np

    array = audio.detach().cpu().numpy() if hasattr(audio, "detach") else np.asarray(audio)
    if array.ndim == 3:
        if array.shape[0] != 1:
            raise DependencyLockError(f"WAV writer supports a single batch item")
        array = array[0]
    if array.ndim != 2:
        raise DependencyLockError("audio must have shape channels x samples")
    channels, samples = array.shape
    if channels not in (1, 2):
        raise DependencyLockError("WAV writer supports mono or stereo")
    interleaved = np.asarray(array.T, dtype="<f4").tobytes(order="C")
    fmt = struct.pack("<HHIIHH", 3, channels, sample_rate, sample_rate * channels * 4, channels * 4, 32)
    fact = struct.pack("<I", samples)
    riff_size = 4 + (8 + len(fmt)) + (8 + len(fact)) + (8 + len(interleaved))
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("wb") as handle:
        handle.write(b"RIFF")
        handle.write(struct.pack("<I", riff_size))
        handle.write(b"WAVE")
        handle.write(b"fmt ")
        handle.write(struct.pack("<I", len(fmt)))
        handle.write(fmt)
        handle.write(b"fact")
        handle.write(struct.pack("<I", len(fact)))
        handle.write(fact)
        handle.write(b"data")
        handle.write(struct.pack("<I", len(interleaved)))
        handle.write(interleaved)


