"""Hardware probe and speech-model choice, without torch."""

from __future__ import annotations

import ctypes
import importlib.util
import os
import sys
from dataclasses import dataclass, replace
from pathlib import Path

# Confirm before CPU transcription expected to run longer than this.
CONFIRM_ABOVE_SECONDS = 10 * 60

FASTER_WHISPER = "faster-whisper"
ONNX_ASR = "onnx-asr"
GIGAAM = "gigaam-v3-e2e-rnnt"  # GigaAM v3 with punctuation, Russian only
_BACKEND_MODULES = {FASTER_WHISPER: "faster_whisper", ONNX_ASR: "onnx_asr"}

# Rough processing time per second of audio, from the backends' published benchmarks.
_SPEED = {
    ("cuda", GIGAAM): 0.02,
    ("cpu", GIGAAM): 0.1,
    ("cuda", "large-v3"): 0.08,
    ("cuda", "large-v3-turbo"): 0.04,
    ("cuda", "medium"): 0.05,
    ("cuda", "small"): 0.03,
    ("cpu", "large-v3"): 2.0,
    ("cpu", "large-v3-turbo"): 1.0,
    ("cpu", "medium"): 1.0,
    ("cpu", "small"): 0.4,
    ("cpu", "base"): 0.2,
    ("cpu", "tiny"): 0.1,
}


@dataclass(frozen=True)
class Gpu:
    name: str | None
    compute_capability: tuple[int, int] | None  # (12, 0) is Blackwell, RTX 50-series
    free_vram_mb: int | None  # None without nvidia-ml-py
    compute_types: frozenset[str]
    cuda_libraries: bool = True  # cuBLAS/cuDNN loadable; a GPU without them is unusable


@dataclass(frozen=True)
class DeviceReport:
    gpus: tuple[Gpu, ...]
    cpu_count: int
    backends: frozenset[str] = frozenset({FASTER_WHISPER})  # installed speech backends


@dataclass(frozen=True)
class TranscriberChoice:
    tier: str
    model: str
    device: str
    compute_type: str
    cpu_threads: int
    backend: str = FASTER_WHISPER

    def describe(self) -> str:
        threads = f", {self.cpu_threads} threads" if self.device == "cpu" else ""
        via = f" via {self.backend}" if self.backend != FASTER_WHISPER else ""
        return f"{self.model} on {self.device} ({self.compute_type}){threads}{via}"

    def estimate_seconds(self, audio_seconds: float) -> float:
        return audio_seconds * _SPEED.get((self.device, self.model), 1.0)


def probe() -> DeviceReport:
    """CUDA devices via ctranslate2 (if installed), VRAM via nvidia-ml-py (if installed),
    and which speech backends are installed."""
    cpu_count = os.cpu_count() or 2
    backends = frozenset(
        name for name, module in _BACKEND_MODULES.items() if _installed(module)
    )
    try:
        import ctranslate2
    except ImportError:
        return DeviceReport(gpus=(), cpu_count=cpu_count, backends=backends)
    gpus = []
    libraries = _cuda_libraries_loadable()
    for index in range(ctranslate2.get_cuda_device_count()):
        types = frozenset(ctranslate2.get_supported_compute_types("cuda", index))
        name, capability, free = _nvml(index)
        gpus.append(Gpu(name=name, compute_capability=capability, free_vram_mb=free,
                        compute_types=types, cuda_libraries=libraries))
    return DeviceReport(gpus=tuple(gpus), cpu_count=cpu_count, backends=backends)


def _installed(module: str) -> bool:
    try:
        return importlib.util.find_spec(module) is not None
    except (ImportError, ValueError):  # ValueError: module set to None in sys.modules
        return False


def choose(report: DeviceReport, *, model: str | None = None, device: str | None = None,
           backend: str | None = None, language: str | None = None) -> TranscriberChoice:
    """The model for this machine and Lecture language; the keyword options override
    the automatic choice. Russian goes to GigaAM when onnx-asr is installed."""
    # Leave half the cores (at most 8 used) so the machine stays usable.
    threads = max(1, min(8, report.cpu_count // 2))
    cpu = TranscriberChoice(tier="cpu", model="small", device="cpu", compute_type="int8",
                            cpu_threads=threads)
    gpu = next((g for g in report.gpus if g.cuda_libraries), None)
    if device == "cpu" or (gpu is None and device != "cuda"):
        choice = cpu
    elif gpu is None:  # --device cuda although none was detected
        choice = TranscriberChoice(tier="gpu_unknown", model="medium", device="cuda",
                                   compute_type="float16", cpu_threads=threads)
    else:
        choice = _gpu_choice(gpu, threads)
    if backend is None:
        backend = ONNX_ASR if language == "ru" and ONNX_ASR in report.backends else FASTER_WHISPER
    if backend == ONNX_ASR:
        choice = replace(choice, backend=ONNX_ASR, model=GIGAAM, compute_type="float32")
    if model:
        choice = replace(choice, model=model)
    return choice


def _gpu_choice(gpu: Gpu, threads: int) -> TranscriberChoice:
    # float16 everywhere on GPU: int8 is disabled on Blackwell in CTranslate2, and
    # float16 is the faithful default elsewhere.
    compute = "float16" if "float16" in gpu.compute_types else "float32"
    free = gpu.free_vram_mb
    if free is None:
        tier, model = "gpu_unknown", "medium"
    elif free >= 8000:
        tier, model = "gpu_large", "large-v3"
    elif free >= 5000:
        tier, model = "gpu_medium", "large-v3-turbo"
    elif free >= 3000:
        tier, model = "gpu_small", "medium"
    else:
        tier, model = "gpu_small", "small"
    return TranscriberChoice(tier=tier, model=model, device="cuda", compute_type=compute,
                             cpu_threads=threads)


CUDA_LIBRARIES_HINT = "pip install nvidia-cublas-cu12 nvidia-cudnn-cu12"
_CUBLAS = {"win32": "cublas64_12.dll", "darwin": ""}.get(sys.platform, "libcublas.so.12")


def _cuda_libraries_loadable() -> bool:
    """Whether CTranslate2 will find cuBLAS (CUDA 12): on the system, or from the
    nvidia-cublas-cu12 wheel."""
    if not _CUBLAS:
        return False
    try:
        ctypes.CDLL(_CUBLAS)
        return True
    except OSError:
        pass
    spec = importlib.util.find_spec("nvidia.cublas") if importlib.util.find_spec("nvidia") else None
    if spec and spec.submodule_search_locations:
        for folder in spec.submodule_search_locations:
            for library in (Path(folder) / "lib").glob(_CUBLAS + "*"):
                try:
                    ctypes.CDLL(str(library))
                    return True
                except OSError:
                    continue
    return False


def _nvml(index: int) -> tuple[str | None, tuple[int, int] | None, int | None]:
    try:
        import pynvml
    except ImportError:
        return None, None, None
    try:
        pynvml.nvmlInit()
        handle = pynvml.nvmlDeviceGetHandleByIndex(index)
        name = pynvml.nvmlDeviceGetName(handle)
        major, minor = pynvml.nvmlDeviceGetCudaComputeCapability(handle)
        free = pynvml.nvmlDeviceGetMemoryInfo(handle).free // (1024 * 1024)
        return (name.decode() if isinstance(name, bytes) else name), (major, minor), int(free)
    except pynvml.NVMLError:
        return None, None, None
