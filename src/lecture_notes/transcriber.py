"""The transcriber interface: audio in, timestamped segments out."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path
from typing import TYPE_CHECKING, Protocol

if TYPE_CHECKING:
    from lecture_notes.hardware import TranscriberChoice


class TranscriptOrigin(StrEnum):
    """Where a Transcript came from, best first."""

    HUMAN_SUBTITLES = "human_subtitles"
    LOCAL_SPEECH_RECOGNITION = "local_speech_recognition"
    AUTO_SUBTITLES = "auto_subtitles"


@dataclass(frozen=True)
class Segment:
    start: float
    end: float
    text: str


@dataclass(frozen=True)
class Transcription:
    language: str
    segments: list[Segment]
    model: str | None  # None for subtitles
    device: str | None  # where it actually ran (a GPU job may fall back to CPU)
    origin: TranscriptOrigin = TranscriptOrigin.LOCAL_SPEECH_RECOGNITION
    compute_type: str | None = None  # as actually run; None: as chosen
    choice: TranscriberChoice | None = None  # the model choice, for local recognition


class Transcriber(Protocol):
    def transcribe(self, audio: Path, language: str | None) -> Transcription:
        """Transcribe a 16 kHz mono WAV. `language=None` means detect it."""
        ...
