from __future__ import annotations

from typing import Any


class AudioMetricsError(RuntimeError):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message


def compute_stem_metrics(torch: Any, source: Any, estimates: Any, *, frame_samples: int = 44100) -> dict[str, Any]:
    """Compute bounded reconstruction and per-stem activity evidence.

    Expected shapes are source=(1, 2, samples) and estimates=(1, 4, 2, samples).
    """
    if getattr(source, "ndim", None) != 3 or tuple(source.shape[:2]) != (1, 2):
        raise AudioMetricsError("INVALID_SOURCE_SHAPE", f"unexpected source shape: {tuple(source.shape)}")
    if getattr(estimates, "ndim", None) != 4 or tuple(estimates.shape[:3]) != (1, 4, 2):
        raise AudioMetricsError("INVALID_STEM_SHAPE", f"unexpected estimate shape: {tuple(estimates.shape)}")
    if estimates.shape[-1] != source.shape[-1]:
        raise AudioMetricsError("INVALID_STEM_SHAPE", "estimate duration differs from source")
    if frame_samples <= 0:
        raise AudioMetricsError("INVALID_FRAME_SIZE", "frame_samples must be positive")
    if source.shape[-1] <= 0:
        raise AudioMetricsError("INVALID_SOURCE_SHAPE", "source must contain at least one sample")
    if not torch.isfinite(source).all().item() or not torch.isfinite(estimates).all().item():
        raise AudioMetricsError("INVALID_STEM_VALUE", "metrics input contains NaN or Inf")

    reconstruction = estimates.sum(dim=1)
    residual = source - reconstruction
    source_energy = torch.mean(source * source)
    residual_energy = torch.mean(residual * residual)
    residual_rms = torch.sqrt(residual_energy)
    residual_energy_ratio = residual_energy / torch.clamp(source_energy, min=1e-24)

    activities: list[dict[str, Any]] = []
    targets = ("vocals", "drums", "bass", "other")
    total_samples = int(source.shape[-1])
    for index, target in enumerate(targets):
        stem = estimates[0, index]
        frames: list[dict[str, Any]] = []
        for start in range(0, total_samples, frame_samples):
            end = min(total_samples, start + frame_samples)
            window = stem[:, start:end]
            if window.shape[-1] <= 0:
                raise AudioMetricsError("INVALID_FRAME_SIZE", f"empty activity frame for {target}")
            rms = float(torch.sqrt(torch.mean(window * window)).item())
            peak = float(torch.max(torch.abs(window)).item())
            frames.append(
                {
                    "start_sample": start,
                    "end_sample": end,
                    "rms": rms,
                    "peak_abs": peak,
                    "evidence_class": "MEASURED",
                }
            )
        activities.append({"target": target, "frames": frames, "evidence_class": "QUALITY_PROXY"})

    return {
        "reconstruction_rms_error": float(residual_rms.item()),
        "residual_to_mix_energy_ratio": float(residual_energy_ratio.item()),
        "stem_activity": activities,
        "evidence_class": "QUALITY_PROXY",
        "authority_transfer": False,
    }
