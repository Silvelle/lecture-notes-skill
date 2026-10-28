"""Source → Lecture bundle."""

from __future__ import annotations

import tempfile
from pathlib import Path

from lecture_notes import bundle, frames, media
from lecture_notes.errors import LectureNotesError
from lecture_notes.transcriber import Transcriber


def extract(
    source: Path,
    out_dir: Path,
    *,
    transcriber: Transcriber | None = None,
    language: str | None = None,
    with_key_frames: bool = True,
    min_frame_interval: float = frames.DEFAULT_MIN_INTERVAL,
) -> Path:
    if not source.is_file():
        raise LectureNotesError(f"{source}: no such file")
    duration = media.probe_duration(source)
    transcriber = transcriber or _default_transcriber()
    with tempfile.TemporaryDirectory() as tmp:
        wav = Path(tmp) / "audio.wav"
        media.extract_audio(source, wav)
        transcription = transcriber.transcribe(wav, language)
    frames.remove_key_frames(out_dir)
    if not with_key_frames:
        key_frames = frames.SKIPPED
    elif not media.has_video(source):
        key_frames = frames.NO_VIDEO
    else:
        key_frames = frames.extract_key_frames(
            source, out_dir, duration=duration, min_interval=min_frame_interval
        )
    bundle.write(out_dir, source=source, duration=duration, transcription=transcription,
                 language_overridden=language is not None, key_frames=key_frames)
    return out_dir


def _default_transcriber() -> Transcriber:
    from lecture_notes.whisper import FasterWhisperTranscriber

    return FasterWhisperTranscriber()
