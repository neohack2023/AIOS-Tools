from __future__ import annotations

import importlib
import math
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .audio_chunking import AudioChunkingError, ChunkProfile, run_chunked_separator
from .audio_metrics import compute_stem_metrics
from .audio_transaction import ArtifactSpec, AudioArtifactTransaction
from .audio_wav import AudioWavError, require_float32_stereo_wav, write_float32_wav

EXPECTED_TARGETS = ["vocals", "drums", "bass", "other"]
EXPECTED_SAMPLE_RATE = 44100
EXPECTED_CHANNELS = 2
LEGACY_WEIGHT_KEYS = {"sample_rate", "stft.window", "transform.0.window"}
FROZEN_CHUNK_PROFILE = ChunkProfile()


class AudioInferenceError(RuntimeError):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message


@dataclass(frozen=True)
class StemMetadata:
    target: str
    sample_rate_hz: int
    channels: int
    samples: int
    duration_seconds: float
    peak_abs: float
    finite: bool


def _require_runtime_modules() -> tuple[Any, Any, Any]:
    try:
        torch = importlib.import_module("torch")
        torchaudio = importlib.import_module("torchaudio")
        openunmix = importlib.import_module("openunmix")
    except ModuleNotFoundError as exc:
        raise AudioInferenceError("MODEL_UNAVAILABLE", f"required runtime dependency is missing: {exc.name}") from exc
    return torch, torchaudio, openunmix


def _load_weight_payload(torch: Any, path: Path) -> dict[str, Any]:
    try:
        payload = torch.load(path, map_location="cpu", weights_only=True)
    except TypeError:
        payload = torch.load(path, map_location="cpu")
    if isinstance(payload, dict) and isinstance(payload.get("state_dict"), dict):
        payload = payload["state_dict"]
    if not isinstance(payload, dict):
        raise AudioInferenceError("MODEL_WEIGHT_INVALID", f"unexpected weight payload: {path.name}")
    return payload


def _filtered_state_dict(model: Any, state_dict: dict[str, Any], target: str) -> dict[str, Any]:
    model_keys = set(model.state_dict())
    state_keys = set(state_dict)
    missing = sorted(model_keys - state_keys)
    extra = sorted(state_keys - model_keys)
    if missing:
        raise AudioInferenceError("MODEL_WEIGHT_INVALID", f"{target} weight is missing model keys: {missing[:8]}")
    if set(extra) != LEGACY_WEIGHT_KEYS:
        raise AudioInferenceError("MODEL_WEIGHT_INVALID", f"{target} weight has unexpected keys: {extra}")
    sample_rate = state_dict.get("sample_rate")
    if sample_rate is None or float(sample_rate) != float(EXPECTED_SAMPLE_RATE):
        raise AudioInferenceError("MODEL_WEIGHT_INVALID", f"{target} weight sample rate is not 44100 Hz")
    return {key: value for key, value in state_dict.items() if key in model_keys}


def _load_frozen_separator(openunmix: Any, torch: Any, model_cache: Path) -> Any:
    try:
        target_models = openunmix.umxhq_spec(targets=EXPECTED_TARGETS, device="cpu", pretrained=False)
    except Exception as exc:
        raise AudioInferenceError("MODEL_UNAVAILABLE", f"failed to construct UMXHQ models: {exc}") from exc
    for target in EXPECTED_TARGETS:
        matches = sorted((model_cache / "weights").glob(f"{target}-*.pth"))
        if len(matches) != 1:
            raise AudioInferenceError("MODEL_WEIGHT_MISSING", f"expected exactly one {target} weight, found {len(matches)}")
        state_dict = _load_weight_payload(torch, matches[0])
        filtered = _filtered_state_dict(target_models[target], state_dict, target)
        incompatible = target_models[target].load_state_dict(filtered, strict=True)
        if incompatible.missing_keys or incompatible.unexpected_keys:
            raise AudioInferenceError("MODEL_WEIGHT_INVALID", f"strict load failed for {target}")
        target_models[target].eval()
    try:
        separator_module = importlib.import_module("openunmix.model")
        separator = separator_module.Separator(
            target_models=target_models,
            niter=1,
            residual=False,
            n_fft=4096,
            n_hop=1024,
            nb_channels=2,
            sample_rate=44100.0,
            wiener_win_len=300,
            filterbank="torch",
        ).to("cpu")
        separator.eval()
        return separator
    except Exception as exc:
        raise AudioInferenceError("MODEL_UNAVAILABLE", f"failed to construct frozen separator: {exc}") from exc


def _decode_stereo_float32(torchaudio: Any, torch: Any, source_path: Path) -> Any:
    try:
        waveform, sample_rate = torchaudio.load(str(source_path))
    except Exception as exc:
        raise AudioInferenceError("FAILED_DECODE", f"audio decode failed: {exc}") from exc
    if waveform.ndim != 2:
        raise AudioInferenceError("FAILED_DECODE", f"decoded waveform must be channels x samples, got {tuple(waveform.shape)}")
    if waveform.shape[0] == 1:
        waveform = waveform.repeat(2, 1)
    elif waveform.shape[0] != 2:
        raise AudioInferenceError("STEM_CHANNEL_MISMATCH", f"source must be mono or stereo, got {waveform.shape[0]} channels")
    waveform = waveform.to(dtype=torch.float32, device="cpu")
    if int(sample_rate) != EXPECTED_SAMPLE_RATE:
        try:
            waveform = torchaudio.functional.resample(waveform, int(sample_rate), EXPECTED_SAMPLE_RATE)
        except Exception as exc:
            raise AudioInferenceError("FAILED_DECODE", f"resample to 44100 Hz failed: {exc}") from exc
    if waveform.shape[-1] <= 0:
        raise AudioInferenceError("FAILED_DECODE", "decoded source is empty")
    if not torch.isfinite(waveform).all().item():
        raise AudioInferenceError("INVALID_STEM_VALUE", "decoded source contains NaN or Inf")
    return waveform.unsqueeze(0).contiguous()


def _validate_estimates(torch: Any, estimates: Any, source: Any) -> list[StemMetadata]:
    expected_shape = (1, 4, 2, int(source.shape[-1]))
    if tuple(estimates.shape) != expected_shape:
        raise AudioInferenceError("INVALID_STEM_SHAPE", f"expected {expected_shape}, got {tuple(estimates.shape)}")
    if not torch.isfinite(estimates).all().item():
        raise AudioInferenceError("INVALID_STEM_VALUE", "stem estimates contain NaN or Inf")
    metadata: list[StemMetadata] = []
    duration = source.shape[-1] / EXPECTED_SAMPLE_RATE
    for index, target in enumerate(EXPECTED_TARGETS):
        stem = estimates[0, index]
        channels = int(stem.shape[0])
        samples = int(stem.shape[-1])
        if channels != EXPECTED_CHANNELS:
            raise AudioInferenceError("STEM_CHANNEL_MISMATCH", f"{target} has {channels} channels")
        if samples != int(source.shape[-1]):
            raise AudioInferenceError("STEM_DURATION_MISMATCH", f"{target} sample count differs from source")
        peak = float(torch.max(torch.abs(stem)).item())
        if not math.isfinite(peak):
            raise AudioInferenceError("INVALID_STEM_VALUE", f"{target} peak is not finite")
        metadata.append(StemMetadata(target, EXPECTED_SAMPLE_RATE, channels, samples, float(duration), peak, True))
    return metadata


def run_frozen_stem_inference(*, source_path: Path, model_cache: Path, transaction: AudioArtifactTransaction) -> dict[str, Any]:
    if transaction.state != "PREPARED":
        raise AudioInferenceError("TRANSACTION_STATE_INVALID", "stem inference requires a prepared transaction")
    torch, torchaudio, openunmix = _require_runtime_modules()
    torch.set_num_threads(1)
    try:
        torch.set_num_interop_threads(1)
    except RuntimeError:
        pass
    torch.manual_seed(0)
    torch.use_deterministic_algorithms(True)
    source = _decode_stereo_float32(torchaudio, torch, source_path)
    separator = _load_frozen_separator(openunmix, torch, model_cache)
    try:
        with torch.inference_mode():
            estimates, chunking = run_chunked_separator(torch, separator, source, profile=FROZEN_CHUNK_PROFILE)
    except AudioChunkingError as exc:
        raise AudioInferenceError(exc.code, exc.message) from exc
    except Exception as exc:
        raise AudioInferenceError("SEPARATION_RUNTIME_ERROR", f"Open-Unmix inference failed: {exc}") from exc
    metadata = _validate_estimates(torch, estimates, source)
    metrics = compute_stem_metrics(torch, source, estimates, frame_samples=EXPECTED_SAMPLE_RATE)
    artifact_specs: list[ArtifactSpec] = []
    staged: list[dict[str, Any]] = []
    for index, item in enumerate(metadata):
        relative = f"stems/{item.target}.wav"
        path = transaction.artifact_path(relative)
        try:
            write_float32_wav(path, estimates[0, index], EXPECTED_SAMPLE_RATE)
            wav_format = require_float32_stereo_wav(path, EXPECTED_SAMPLE_RATE, item.samples)
        except AudioWavError as exc:
            raise AudioInferenceError(exc.code, exc.message) from exc
        artifact_specs.append(ArtifactSpec(relative, "audio/wav", "MODEL_ESTIMATE"))
        staged.append({
            "target": item.target,
            "relative_path": relative,
            "sample_rate_hz": item.sample_rate_hz,
            "channels": item.channels,
            "samples": item.samples,
            "duration_seconds": item.duration_seconds,
            "peak_abs": item.peak_abs,
            "finite": item.finite,
            "wav_format": wav_format,
            "evidence_class": "MODEL_ESTIMATE",
        })
    return {
        "status": "STEMS_STAGED",
        "targets": list(EXPECTED_TARGETS),
        "stems": staged,
        "metrics": metrics,
        "chunking": chunking,
        "artifact_specs": artifact_specs,
        "runtime_admission": False,
        "pilot_authorized": False,
        "authority_transfer": False,
    }
