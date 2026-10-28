"""`lecture-notes doctor`: report what this machine can do."""

from __future__ import annotations

import importlib.util
import shutil

from lecture_notes import hardware, ocr
from lecture_notes.hardware import DeviceReport

JS_RUNTIMES = ("deno", "node", "bun")


def report(device_report: DeviceReport | None = None) -> tuple[list[str], bool]:
    """Report lines, and whether everything `extract` strictly needs is present."""
    device_report = device_report or hardware.probe()
    choice = hardware.choose(device_report)
    lines = [_line("hardware tier", f"{choice.tier}{_gpu_detail(device_report)}"),
             _line("default model", choice.describe())]
    ffmpeg_ok = all(shutil.which(tool) for tool in ("ffmpeg", "ffprobe"))
    lines.append(_line("ffmpeg", "ok" if ffmpeg_ok else "missing: install ffmpeg (https://ffmpeg.org)"))
    runtime = next((name for name in JS_RUNTIMES if shutil.which(name)), None)
    lines.append(_line(
        "JS runtime",
        f"ok ({runtime})" if runtime
        else "missing: YouTube needs one; install deno (https://deno.land)",
    ))
    lines.append(_line("yt-dlp", _module_status("yt_dlp", "URL Sources")))
    for name, backend in hardware.BACKENDS.items():
        installed = name in device_report.backends
        lines.append(_line(name, "ok" if installed else f"missing: {backend.install_hint(name)}"))
    lines.append(_line("tesseract", _tesseract_status()))
    return lines, ffmpeg_ok


def _tesseract_status() -> str:
    if shutil.which("tesseract") is None:
        return "missing (optional OCR of Key frames): install tesseract-ocr"
    languages = ocr.installed_languages()
    status = f"ok ({', '.join(languages)})"
    if "eng" not in languages:
        status += "; missing English: install tesseract-ocr-eng"
    if "rus" not in languages:
        status += "; more languages: install tesseract-ocr-rus (or your Lecture's language)"
    if importlib.util.find_spec("pytesseract") is None:
        status += "; pip install 'lecture-notes[ocr]'"
    return status


def _gpu_detail(report: DeviceReport) -> str:
    if not report.gpus:
        return f" ({report.cpu_count} CPU threads, no CUDA GPU)"
    gpu = report.gpus[0]
    parts = [gpu.name or "CUDA GPU"]
    if not gpu.cuda_libraries:
        parts.append(f"unusable: CUDA libraries missing; {hardware.CUDA_LIBRARIES_HINT}")
    if gpu.free_vram_mb is not None:
        parts.append(f"{gpu.free_vram_mb / 1024:.1f} GB free")
    else:
        parts.append("VRAM unknown: pip install nvidia-ml-py")
    if gpu.compute_capability:
        parts.append("sm_{}{}".format(*gpu.compute_capability))
    return f" ({', '.join(parts)})"


def _module_status(module: str, purpose: str) -> str:
    return "ok" if importlib.util.find_spec(module) else f"missing ({purpose})"


def _line(name: str, status: str) -> str:
    return f"{name + ':':<16}{status}"
