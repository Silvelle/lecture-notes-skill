"""The transcriber interface: audio in, timestamped segments out."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Protocol


@dataclass(frozen=True)
class Segment:
    start: float
    end: float
    text: str


@dataclass(frozen=True)
class Transcription:
    language: str
    segments: list[Segment]
    model: str
    device: str


class Transcriber(Protocol):
    def transcribe(self, audio: Path, language: str | None) -> Transcription:
        """Transcribe a 16 kHz mono WAV. `language=None` means detect it."""
        ...
