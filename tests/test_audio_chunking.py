from __future__ import annotations

import pytest

from aios_tools.audio_chunking import AudioChunkingError, ChunkProfile, build_chunk_plan, run_chunked_separator


def test_frozen_chunk_plan_is_ordered_and_covers_tail():
    profile = ChunkProfile(sample_rate_hz=10, chunk_seconds=4, overlap_seconds=1)
    plan = build_chunk_plan(95, profile)
    assert [item["index"] for item in plan] == list(range(len(plan)))
    assert plan[0] == {"index": 0, "start_sample": 0, "end_sample": 40, "valid_samples": 40, "padded_samples": 0}
    assert plan[-1]["end_sample"] == 95
    assert plan[-1]["padded_samples"] == 35
    assert all(left["start_sample"] < right["start_sample"] for left, right in zip(plan, plan[1:]))


def test_identity_separator_recombines_exact_source_shape_and_values():
    torch = pytest.importorskip("torch")
    profile = ChunkProfile(sample_rate_hz=10, chunk_seconds=4, overlap_seconds=1)
    source = torch.arange(2 * 95, dtype=torch.float32).reshape(1, 2, 95) / 100.0

    def separator(chunk):
        return chunk.unsqueeze(1).repeat(1, 4, 1, 1)

    output, receipt = run_chunked_separator(torch, separator, source, profile=profile)
    assert tuple(output.shape) == (1, 4, 2, 95)
    for index in range(4):
        assert torch.allclose(output[:, index], source, atol=1e-6, rtol=0)
    assert receipt["output_samples"] == 95
    assert receipt["chunk_count"] == len(build_chunk_plan(95, profile))
    assert receipt["authority_transfer"] is False


def test_invalid_overlap_is_rejected():
    with pytest.raises(AudioChunkingError, match="overlap"):
        build_chunk_plan(100, ChunkProfile(sample_rate_hz=10, chunk_seconds=2, overlap_seconds=2))


def test_wrong_separator_shape_fails_closed():
    torch = pytest.importorskip("torch")
    source = torch.zeros((1, 2, 30), dtype=torch.float32)
    profile = ChunkProfile(sample_rate_hz=10, chunk_seconds=2, overlap_seconds=1)

    def separator(chunk):
        return torch.zeros((1, 3, 2, chunk.shape[-1]), dtype=chunk.dtype)

    with pytest.raises(AudioChunkingError, match="expected"):
        run_chunked_separator(torch, separator, source, profile=profile)


def test_nonfinite_chunk_fails_closed():
    torch = pytest.importorskip("torch")
    source = torch.zeros((1, 2, 30), dtype=torch.float32)
    profile = ChunkProfile(sample_rate_hz=10, chunk_seconds=2, overlap_seconds=1)

    def separator(chunk):
        result = torch.zeros((1, 4, 2, chunk.shape[-1]), dtype=chunk.dtype)
        result[..., 0] = float("nan")
        return result

    with pytest.raises(AudioChunkingError, match="NaN or Inf"):
        run_chunked_separator(torch, separator, source, profile=profile)
