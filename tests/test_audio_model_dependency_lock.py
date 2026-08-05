from __future__ import annotations

import importlib.util
import json
import struct
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SCRIPT_PATH = ROOT / "scripts/lock_audio_model_dependencies.py"

spec = importlib.util.spec_from_file_location("lock_audio_model_dependencies", SCRIPT_PATH)
assert spec and spec.loader
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


def test_canonical_profile_hash_is_order_independent():
    left = {"b": 2, "a": {"y": 2, "x": 1}}
    right = {"a": {"x": 1, "y": 2}, "b": 2}
    assert module.canonical_sha256(left) == module.canonical_sha256(right)


def test_fetch_allowlist_rejects_non_https_and_unknown_hosts():
    with pytest.raises(module.DependencyLockError, match="HTTPS"):
        module.assert_allowed_url("http://zenodo.org/example")
    with pytest.raises(module.DependencyLockError, match="not allowlisted"):
        module.assert_allowed_url("https://example.com/model.pth")


def test_runtime_review_fails_closed_when_audio_tool_is_absent(tmp_path: Path):
    for relative in (
        "registry/tools.v0.1.json",
        "policies/execution-policy.v0.1.json",
        "src/aios_tools/tools.py",
        "src/aios_tools/runner.py",
    ):
        path = tmp_path / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("{}\n", encoding="utf-8")
    (tmp_path / "contracts").mkdir()
    output = tmp_path / "review.json"
    args = type("Args", (), {"repo_root": tmp_path, "output": output})()
    assert module.run_review_runtime(args) == 0
    review = json.loads(output.read_text(encoding="utf-8"))
    assert review["implementation_present"] is False
    assert review["runtime_admission"] is False
    assert review["pilot_authorized"] is False
    assert review["decision"] == "SEPARATE_BOUNDED_RUNTIME_IMPLEMENTATION_PR_REQUIRED"


def test_float32_wav_writer_records_ieee_float_format(tmp_path: Path):
    np = pytest.importorskip("numpy")
    audio = np.zeros((2, 64), dtype=np.float32)
    path = tmp_path / "fixture.wav"
    module.write_float32_wav(path, audio, 44100)
    payload = path.read_bytes()
    assert payload[:4] == b"RIFF"
    assert payload[8:12] == b"WAVE"
    fmt_index = payload.index(b"fmt ")
    format_code = struct.unpack_from("<H", payload, fmt_index + 8)[0]
    assert format_code == 3
    assert b"fact" in payload
    assert b"data" in payload
