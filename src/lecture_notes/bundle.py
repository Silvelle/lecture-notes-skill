"""Write a Lecture bundle folder: Manifest + Transcript (JSON and Markdown)."""

from __future__ import annotations

import json
from collections.abc import Sequence
from dataclasses import asdict
from pathlib import Path
from typing import Any

from lecture_notes import __version__
from lecture_notes.frames import KeyFrame, KeyFrames
from lecture_notes.transcriber import Segment, Transcription

SCHEMA_VERSION = 1
MANIFEST = "manifest.json"
TRANSCRIPT_JSON = "transcript.json"
TRANSCRIPT_MARKDOWN = "transcript.md"
PARAGRAPH_PAUSE = 3.0  # seconds of silence that start a new paragraph
PARAGRAPH_SPAN = 60.0  # longest a paragraph runs before a new timestamp


def write(
    out_dir: Path,
    *,
    source: dict[str, str],
    title: str,
    channel: str | None,
    duration: float,
    transcription: Transcription,
    language_overridden: bool,
    key_frames: KeyFrames,
) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    choice = transcription.choice
    _write_json(
        out_dir / MANIFEST,
        {
            "schema_version": SCHEMA_VERSION,
            "tool_version": __version__,
            "source": source,
            "title": title,
            "channel": channel,
            "duration": round(duration, 3),
            "language": transcription.language,
            "language_origin": "user" if language_overridden else "detected",
            "transcript_origin": transcription.origin,
            "backend": choice.backend if choice else None,
            "model": transcription.model,
            "device": transcription.device,
            "compute_type": transcription.compute_type or (choice.compute_type if choice else None),
            "hardware_tier": choice.tier if choice else None,
            "key_frames": asdict(key_frames),
            "files": {"transcript_json": TRANSCRIPT_JSON, "transcript_markdown": TRANSCRIPT_MARKDOWN},
        },
    )
    _write_json(
        out_dir / TRANSCRIPT_JSON,
        {"language": transcription.language, "segments": [asdict(s) for s in transcription.segments]},
    )
    (out_dir / TRANSCRIPT_MARKDOWN).write_text(
        transcript_markdown(title, transcription.segments, key_frames.frames, out_dir),
        encoding="utf-8",
    )


def transcript_markdown(title: str, segments: list[Segment], frames: Sequence[KeyFrame] = (),
                        bundle_dir: Path | None = None) -> str:
    """The whole Lecture as one readable page: paragraphs with their start time, split at
    pauses, every minute and at each slide change, with each Key frame (and its OCR
    text, if any) shown before the speech that runs while it is on screen."""
    pending = sorted(frames, key=lambda f: f.time)
    blocks = [f"# {title}"]
    paragraph: list[Segment] = []

    def flush() -> None:
        if paragraph:
            text = " ".join(s.text.strip() for s in paragraph)
            blocks.append(f"**[{format_timestamp(paragraph[0].start)}]** {text}")
            paragraph.clear()

    for segment in segments:
        shown = []
        while pending and pending[0].time < segment.end:
            shown.append(pending.pop(0))
        if shown or (paragraph and (
            segment.start - paragraph[-1].end > PARAGRAPH_PAUSE
            or segment.start - paragraph[0].start > PARAGRAPH_SPAN
        )):
            flush()
        blocks.extend(_frame_block(frame, bundle_dir) for frame in shown)
        paragraph.append(segment)
    flush()
    blocks.extend(_frame_block(frame, bundle_dir) for frame in pending)
    return "\n\n".join(blocks) + "\n"


def _frame_block(frame: KeyFrame, bundle_dir: Path | None) -> str:
    block = f"![{format_timestamp(frame.time)}]({frame.file})"
    if frame.ocr_text and bundle_dir is not None:
        text = (bundle_dir / frame.ocr_text).read_text(encoding="utf-8").strip()
        if text:
            fence = "```"
            while fence in text:
                fence += "`"
            block += f"\n\n{fence}text\n{text}\n{fence}"
    return block


def format_timestamp(seconds: float) -> str:
    """`mm:ss` under an hour, `h:mm:ss` from an hour on."""
    total = int(seconds)
    hours, rest = divmod(total, 3600)
    minutes, secs = divmod(rest, 60)
    return f"{hours}:{minutes:02d}:{secs:02d}" if hours else f"{minutes:02d}:{secs:02d}"


def _write_json(path: Path, data: Any) -> None:
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
