"""ffmpeg/ffprobe wrappers for local media files."""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

from lecture_notes.errors import LectureNotesError


def probe_duration(path: Path) -> float:
    """Duration of a media file in seconds."""
    result = subprocess.run(
        [_tool("ffprobe"), "-v", "error", "-show_entries", "format=duration",
         "-of", "default=noprint_wrappers=1:nokey=1", str(path)],
        capture_output=True, text=True,
    )
    try:
        return float(result.stdout.strip())
    except ValueError:
        raise LectureNotesError(f"{path} is not a readable video or audio file") from None


def extract_audio(path: Path, wav: Path) -> None:
    """Write the file's audio as 16 kHz mono WAV, the format every transcriber takes."""
    result = subprocess.run(
        [_tool("ffmpeg"), "-y", "-loglevel", "error", "-i", str(path),
         "-vn", "-ac", "1", "-ar", "16000", "-c:a", "pcm_s16le", str(wav)],
        capture_output=True, text=True,
    )
    if result.returncode != 0:
        raise LectureNotesError(f"{path} has no readable audio track")


def _tool(name: str) -> str:
    found = shutil.which(name)
    if found is None:
        raise LectureNotesError(f"{name} not found on PATH; install ffmpeg (https://ffmpeg.org) and retry")
    return found
