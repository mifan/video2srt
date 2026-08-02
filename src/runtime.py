from dataclasses import dataclass
import gc

import torch


@dataclass(frozen=True)
class InferenceRuntime:
    device: str
    dtype: torch.dtype


def resolve_inference_runtime(requested_device="auto"):
    """Select a supported torch device and a safe inference precision."""
    device = _resolve_device(requested_device)

    if device.startswith("cuda"):
        if _cuda_supports_bfloat16():
            return InferenceRuntime(device=device, dtype=torch.bfloat16)
        return InferenceRuntime(device=device, dtype=torch.float16)

    if device == "mps":
        return InferenceRuntime(device=device, dtype=torch.float16)

    return InferenceRuntime(device=device, dtype=torch.float32)


def _resolve_device(requested_device):
    if requested_device == "auto":
        if torch.cuda.is_available():
            return "cuda:0"
        if _mps_is_available():
            return "mps"
        return "cpu"

    device = str(requested_device)
    if device.startswith("cuda") and not torch.cuda.is_available():
        raise RuntimeError(f"CUDA device requested but unavailable: {device}")

    if device == "mps" and not _mps_is_available():
        raise RuntimeError("MPS device requested but unavailable")

    return device


def _cuda_supports_bfloat16():
    checker = getattr(torch.cuda, "is_bf16_supported", None)
    return bool(checker and checker())


def _mps_is_available():
    mps = getattr(torch.backends, "mps", None)
    return bool(mps and mps.is_available())


def release_accelerator_memory():
    """Collect Python objects and return cached accelerator memory when possible."""
    gc.collect()

    if torch.cuda.is_available():
        torch.cuda.empty_cache()
        return

    mps = getattr(torch, "mps", None)
    empty_cache = getattr(mps, "empty_cache", None)
    if empty_cache:
        empty_cache()
