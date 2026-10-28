"""`lecture-notes doctor`: report what this machine can do."""

from __future__ import annotations

import importlib.util
import shutil

JS_RUNTIMES = ("deno", "node", "bun")


def report() -> tuple[list[str], bool]:
    """Report lines, and whether everything `extract` strictly needs is present."""
    lines: list[str] = []
    ffmpeg_ok = all(shutil.which(tool) for tool in ("ffmpeg", "ffprobe"))
    lines.append(_line("ffmpeg", "ok" if ffmpeg_ok else "missing: install ffmpeg (https://ffmpeg.org)"))
    runtime = next((name for name in JS_RUNTIMES if shutil.which(name)), None)
    lines.append(_line(
        "JS runtime",
        f"ok ({runtime})" if runtime
        else "missing: YouTube needs one; install deno (https://deno.land)",
    ))
    lines.append(_line("yt-dlp", _module_status("yt_dlp", "URL Sources")))
    lines.append(_line("faster-whisper", _module_status(
        "faster_whisper", "speech recognition; pip install 'lecture-notes[whisper]'"
    )))
    return lines, ffmpeg_ok


def _module_status(module: str, purpose: str) -> str:
    return "ok" if importlib.util.find_spec(module) else f"missing ({purpose})"


def _line(name: str, status: str) -> str:
    return f"{name + ':':<16}{status}"
