"""Write a Lecture bundle folder: Manifest + Transcript (JSON and Markdown)."""

from __future__ import annotations

import json
from dataclasses import asdict
from pathlib import Path
from typing import Any

from lecture_notes import __version__
from lecture_notes.frames import KeyFrames
from lecture_notes.transcriber import Segment, Transcription

SCHEMA_VERSION = 1
PARAGRAPH_PAUSE = 3.0  # seconds of silence that start a new paragraph
PARAGRAPH_SPAN = 60.0  # longest a paragraph runs before a new timestamp


def write(
    out_dir: Path,
    *,
    source: Path,
    duration: float,
    transcription: Transcription,
    language_overridden: bool,
    key_frames: KeyFrames,
) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    _write_json(
        out_dir / "manifest.json",
        {
            "schema_version": SCHEMA_VERSION,
            "tool_version": __version__,
            "source": {"kind": "local_file", "path": str(source.resolve())},
            "title": source.stem,
            "duration": round(duration, 3),
            "language": transcription.language,
            "language_origin": "user" if language_overridden else "detected",
            "transcript_origin": "local_speech_recognition",
            "model": transcription.model,
            "device": transcription.device,
            "key_frames": asdict(key_frames),
            "files": {"transcript_json": "transcript.json", "transcript_markdown": "transcript.md"},
        },
    )
    _write_json(
        out_dir / "transcript.json",
        {"language": transcription.language, "segments": [asdict(s) for s in transcription.segments]},
    )
    (out_dir / "transcript.md").write_text(
        transcript_markdown(source.stem, transcription.segments), encoding="utf-8"
    )


def transcript_markdown(title: str, segments: list[Segment]) -> str:
    """Readable Transcript: paragraphs split at pauses or every minute, each with its start time."""
    paragraphs: list[list[Segment]] = []
    for segment in segments:
        current = paragraphs[-1] if paragraphs else None
        if (
            current is None
            or segment.start - current[-1].end > PARAGRAPH_PAUSE
            or segment.start - current[0].start > PARAGRAPH_SPAN
        ):
            paragraphs.append([segment])
        else:
            current.append(segment)
    blocks = [f"# {title}"] + [
        f"**[{format_timestamp(p[0].start)}]** " + " ".join(s.text.strip() for s in p)
        for p in paragraphs
    ]
    return "\n\n".join(blocks) + "\n"


def format_timestamp(seconds: float) -> str:
    """`mm:ss` under an hour, `h:mm:ss` from an hour on."""
    total = int(seconds)
    hours, rest = divmod(total, 3600)
    minutes, secs = divmod(rest, 60)
    return f"{hours}:{minutes:02d}:{secs:02d}" if hours else f"{minutes:02d}:{secs:02d}"


def _write_json(path: Path, data: Any) -> None:
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
