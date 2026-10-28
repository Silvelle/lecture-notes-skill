"""ffmpeg/ffprobe wrappers for local media files."""

from __future__ import annotations

import shutil
import subprocess
import wave
from pathlib import Path
from typing import Any

from lecture_notes.errors import LectureNotesError


def probe_duration(path: Path) -> float:
    """Duration of a media file in seconds."""
    result = subprocess.run(
        [tool("ffprobe"), "-v", "error", "-show_entries", "format=duration",
         "-of", "default=noprint_wrappers=1:nokey=1", str(path)],
        capture_output=True, text=True,
    )
    try:
        return float(result.stdout.strip())
    except ValueError:
        raise LectureNotesError(f"{path} is not a readable video or audio file") from None


def has_video(path: Path) -> bool:
    """Whether the file has a real video stream (cover art in audio files doesn't count)."""
    result = subprocess.run(
        [tool("ffprobe"), "-v", "error", "-select_streams", "v",
         "-show_entries", "stream_disposition=attached_pic", "-of", "csv=p=0", str(path)],
        capture_output=True, text=True,
    )
    return any(line.strip() == "0" for line in result.stdout.splitlines())


def extract_audio(path: Path, wav: Path) -> None:
    """Write the file's audio as 16 kHz mono WAV, the format every transcriber takes."""
    result = subprocess.run(
        [tool("ffmpeg"), "-y", "-loglevel", "error", "-i", str(path),
         "-vn", "-ac", "1", "-ar", "16000", "-c:a", "pcm_s16le", str(wav)],
        capture_output=True, text=True,
    )
    if result.returncode != 0:
        raise LectureNotesError(f"{path} has no readable audio track")


def tool(name: str) -> str:
    found = shutil.which(name)
    if found is None:
        raise LectureNotesError(f"{name} not found on PATH; install ffmpeg (https://ffmpeg.org) and retry")
    return found


def read_wav(path: Path) -> Any:
    """16 kHz mono s16le WAV (from `extract_audio`) as float32 samples.

    Backends get samples rather than a path: faster-whisper 1.2.1 opens files with an
    argument newer PyAV releases reject.
    """
    import numpy as np

    with wave.open(str(path), "rb") as wav:
        frames = wav.readframes(wav.getnframes())
    return np.frombuffer(frames, dtype=np.int16).astype(np.float32) / 32768.0
