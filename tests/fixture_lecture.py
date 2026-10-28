"""Render a short fixture Lecture: slides with distinct code text plus a speech track.

Speech is synthesised with espeak-ng when it is installed; otherwise each slide gets
a plain tone, which is enough for tests that use a fake transcriber.
"""

from __future__ import annotations

import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path

from lecture_notes.media import probe_duration


@dataclass(frozen=True)
class Slide:
    code: str
    speech: str


DEFAULT_SLIDES = [
    Slide(code='a = 1\nprint(a)', speech="First we assign one to a and print it."),
    Slide(code='if a == 1:\n    print("one")', speech="Then we check whether a equals one."),
    Slide(code='else:\n    print("a is not 1")', speech="Otherwise we print that a is not one."),
]


def has_tts() -> bool:
    return shutil.which("espeak-ng") is not None


def make_lecture(
    out_dir: Path,
    slides: list[Slide] = DEFAULT_SLIDES,
    seconds_per_slide: float = 2.0,
    speech: bool | None = None,
) -> Path:
    """Write `lecture.mp4` into `out_dir` and return its path."""
    speech = has_tts() if speech is None else speech
    out_dir.mkdir(parents=True, exist_ok=True)
    font = _monospace_font()
    clips: list[Path] = []
    for i, slide in enumerate(slides):
        text_file = out_dir / f"slide_{i}.txt"
        text_file.write_text(slide.code, encoding="utf-8")
        if speech:
            wav = out_dir / f"slide_{i}.wav"
            _run(["espeak-ng", "-w", str(wav), slide.speech])
            duration = max(seconds_per_slide, probe_duration(wav) + 0.5)
            audio_in = ["-i", str(wav)]
            audio_filter = ["-af", "apad"]
        else:
            duration = seconds_per_slide
            audio_in = ["-f", "lavfi", "-i", f"sine=frequency=440:duration={duration}"]
            audio_filter = []
        clip = out_dir / f"slide_{i}.mp4"
        drawtext = (
            f"drawtext=fontfile={font}:textfile={text_file}:"
            "fontcolor=black:fontsize=28:x=40:y=40"
        )
        _run(
            ["ffmpeg", "-y", "-loglevel", "error",
             "-f", "lavfi", "-i", f"color=c=white:s=640x360:r=10:d={duration}",
             *audio_in, *audio_filter,
             "-vf", drawtext, "-t", str(duration),
             "-c:v", "libx264", "-pix_fmt", "yuv420p", "-c:a", "aac", "-ar", "16000",
             str(clip)]
        )
        clips.append(clip)
    concat_list = out_dir / "clips.txt"
    concat_list.write_text("".join(f"file '{c.name}'\n" for c in clips), encoding="utf-8")
    lecture = out_dir / "lecture.mp4"
    _run(["ffmpeg", "-y", "-loglevel", "error", "-f", "concat", "-safe", "0",
          "-i", str(concat_list), "-c", "copy", str(lecture)])
    return lecture


def _monospace_font() -> str:
    result = subprocess.run(
        ["fc-match", "-f", "%{file}", "monospace"], capture_output=True, text=True, check=True
    )
    return result.stdout.strip()


def _run(cmd: list[str]) -> None:
    subprocess.run(cmd, check=True)
