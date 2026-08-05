from __future__ import annotations

import pytest

from aios_tools.audio_metrics import AudioMetricsError, compute_stem_metrics


def test_metrics_reject_extra_rank():
    torch = pytest.importorskip("torch")
    source = torch.zeros((1, 2, 3, 16), dtype=torch.float32)
    estimates = torch.zeros((1, 4, 2, 3, 16), dtype=torch.float32)
    with pytest.raises(AudioMetricsError, match="unexpected source shape"):
        compute_stem_metrics(torch, source, estimates, frame_samples=8)


def test_energy_ratio_is_mean_square_ratio():
    torch = pytest.importorskip("torch")
    source = torch.ones((1, 2, 16), dtype=torch.float32)
    estimates = torch.zeros((1, 4, 2, 16), dtype=torch.float32)
    estimates[:, 0] = 0.5
    result = compute_stem_metrics(torch, source, estimates, frame_samples=8)
    assert result["reconstruction_rms_error"] == pytest.approx(0.5)
    assert result["residual_to_mix_energy_ratio"] == pytest.approx(0.25)
    assert result["authority_transfer"] is False


def test_activity_frames_cover_source_without_empty_windows():
    torch = pytest.importorskip("torch")
    source = torch.ones((1, 2, 10), dtype=torch.float32)
    estimates = torch.zeros((1, 4, 2, 10), dtype=torch.float32)
    estimates[:, 0] = 1.0
    result = compute_stem_metrics(torch, source, estimates, frame_samples=4)
    frames = result["stem_activity"][0]["frames"]
    assert [(frame["start_sample"], frame["end_sample"]) for frame in frames] == [(0, 4), (4, 8), (8, 10)]
