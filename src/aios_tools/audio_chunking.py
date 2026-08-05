from __future__ import annotations

from dataclasses import dataclass
from typing import Any


class AudioChunkingError(RuntimeError):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message


@dataclass(frozen=True)
class ChunkProfile:
    sample_rate_hz: int = 44100
    chunk_seconds: int = 15
    overlap_seconds: int = 2
    pad_final_chunk: bool = True
    recombination: str = "linear_crossfade_weighted_average"
    ordering: str = "ascending_start_sample"

    @property
    def chunk_samples(self) -> int:
        return self.sample_rate_hz * self.chunk_seconds

    @property
    def overlap_samples(self) -> int:
        return self.sample_rate_hz * self.overlap_seconds

    @property
    def hop_samples(self) -> int:
        return self.chunk_samples - self.overlap_samples

    def validate(self) -> None:
        if self.sample_rate_hz <= 0 or self.chunk_seconds <= 0:
            raise AudioChunkingError("CHUNK_PROFILE_INVALID", "sample rate and chunk duration must be positive")
        if self.overlap_seconds < 0 or self.overlap_samples >= self.chunk_samples:
            raise AudioChunkingError("CHUNK_PROFILE_INVALID", "overlap must be non-negative and smaller than the chunk")


def build_chunk_plan(total_samples: int, profile: ChunkProfile) -> list[dict[str, int]]:
    profile.validate()
    if total_samples <= 0:
        raise AudioChunkingError("CHUNK_PROFILE_INVALID", "source must contain samples")
    plan: list[dict[str, int]] = []
    start = 0
    index = 0
    while start < total_samples:
        end = min(total_samples, start + profile.chunk_samples)
        plan.append(
            {
                "index": index,
                "start_sample": start,
                "end_sample": end,
                "valid_samples": end - start,
                "padded_samples": profile.chunk_samples - (end - start),
            }
        )
        index += 1
        start += profile.hop_samples
    return plan


def _chunk_weight(torch: Any, *, valid_samples: int, overlap_samples: int, has_left: bool, has_right: bool, device: Any, dtype: Any) -> Any:
    weight = torch.ones(valid_samples, device=device, dtype=dtype)
    fade = min(overlap_samples, valid_samples)
    if fade > 0 and has_left:
        weight[:fade] = torch.linspace(0.0, 1.0, fade, device=device, dtype=dtype)
    if fade > 0 and has_right:
        weight[-fade:] = torch.minimum(
            weight[-fade:],
            torch.linspace(1.0, 0.0, fade, device=device, dtype=dtype),
        )
    return weight


def run_chunked_separator(torch: Any, separator: Any, source: Any, *, profile: ChunkProfile | None = None) -> tuple[Any, dict[str, Any]]:
    """Run deterministic, bounded overlap-add inference over a full source tensor.

    Expected source shape is (1, 2, samples). Output shape is (1, 4, 2, samples).
    """
    profile = profile or ChunkProfile()
    profile.validate()
    if getattr(source, "ndim", None) != 3 or tuple(source.shape[:2]) != (1, 2):
        raise AudioChunkingError("INVALID_SOURCE_SHAPE", f"unexpected source shape: {tuple(source.shape)}")
    total_samples = int(source.shape[-1])
    plan = build_chunk_plan(total_samples, profile)
    output = torch.zeros((1, 4, 2, total_samples), dtype=source.dtype, device=source.device)
    weight_sum = torch.zeros(total_samples, dtype=source.dtype, device=source.device)
    chunk_receipts: list[dict[str, Any]] = []

    for item in plan:
        start = item["start_sample"]
        end = item["end_sample"]
        valid = item["valid_samples"]
        chunk = source[..., start:end]
        if item["padded_samples"]:
            chunk = torch.nn.functional.pad(chunk, (0, item["padded_samples"]))
        estimates = separator(chunk)
        expected_shape = (1, 4, 2, profile.chunk_samples)
        if tuple(estimates.shape) != expected_shape:
            raise AudioChunkingError("INVALID_STEM_SHAPE", f"chunk {item['index']} expected {expected_shape}, got {tuple(estimates.shape)}")
        if not torch.isfinite(estimates).all().item():
            raise AudioChunkingError("INVALID_STEM_VALUE", f"chunk {item['index']} contains NaN or Inf")
        estimates = estimates[..., :valid]
        weight = _chunk_weight(
            torch,
            valid_samples=valid,
            overlap_samples=profile.overlap_samples,
            has_left=item["index"] > 0,
            has_right=item["index"] < len(plan) - 1,
            device=source.device,
            dtype=source.dtype,
        )
        output[..., start:end] += estimates * weight.view(1, 1, 1, -1)
        weight_sum[start:end] += weight
        chunk_receipts.append({**item, "finite": True})

    if not torch.all(weight_sum > 0).item():
        raise AudioChunkingError("CHUNK_RECOMBINATION_FAILED", "recombination left uncovered samples")
    output = output / weight_sum.view(1, 1, 1, -1)
    if not torch.isfinite(output).all().item():
        raise AudioChunkingError("CHUNK_RECOMBINATION_FAILED", "recombined output contains NaN or Inf")
    receipt = {
        "profile": {
            "sample_rate_hz": profile.sample_rate_hz,
            "chunk_seconds": profile.chunk_seconds,
            "overlap_seconds": profile.overlap_seconds,
            "chunk_samples": profile.chunk_samples,
            "overlap_samples": profile.overlap_samples,
            "hop_samples": profile.hop_samples,
            "pad_final_chunk": profile.pad_final_chunk,
            "recombination": profile.recombination,
            "ordering": profile.ordering,
        },
        "chunk_count": len(plan),
        "chunks": chunk_receipts,
        "output_samples": total_samples,
        "evidence_class": "EXECUTION_CONTROL",
        "authority_transfer": False,
    }
    return output, receipt
