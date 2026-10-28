"""Source → Lecture bundle."""

from __future__ import annotations

import tempfile
from pathlib import Path

from lecture_notes import bundle, media
from lecture_notes.errors import LectureNotesError
from lecture_notes.transcriber import Transcriber


def extract(
    source: Path,
    out_dir: Path,
    *,
    transcriber: Transcriber | None = None,
    language: str | None = None,
) -> Path:
    if not source.is_file():
        raise LectureNotesError(f"{source}: no such file")
    duration = media.probe_duration(source)
    transcriber = transcriber or _default_transcriber()
    with tempfile.TemporaryDirectory() as tmp:
        wav = Path(tmp) / "audio.wav"
        media.extract_audio(source, wav)
        transcription = transcriber.transcribe(wav, language)
    bundle.write(out_dir, source=source, duration=duration, transcription=transcription,
                 language_overridden=language is not None)
    return out_dir


def _default_transcriber() -> Transcriber:
    from lecture_notes.whisper import FasterWhisperTranscriber

    return FasterWhisperTranscriber()
