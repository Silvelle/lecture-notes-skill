"""The Faithfulness check: every idea in a Lecture note cites the Lecture bundle.

The rules and the `--json` format are documented in docs/verify.md.
"""

from __future__ import annotations

import json
import re
from collections.abc import Iterator
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path
from typing import Any

from lecture_notes.bundle import format_timestamp
from lecture_notes.errors import LectureNotesError

# [12:34] or [1:02:05], optionally a link: [12:34](https://youtu.be/x?t=754)
TIMESTAMP = re.compile(r"(?<!\[)\[(?:(\d+):)?(\d+):([0-5]\d)\](?!\])(?:\(<?([^)\s>]*)>?\))?")
WIKI_EMBED = re.compile(r"!\[\[([^\]|#]+)(?:[|#][^\]]*)?\]\]")
MARKDOWN_IMAGE = re.compile(r"!\[[^\]]*\]\(<?([^)\s>]+)>?[^)]*\)")
HTML_IMAGE = re.compile(r"<img\b[^>]*\bsrc\s*=\s*[\"']?([^\"'\s>]+)", re.IGNORECASE)
# YouTube-style time parameter: t=754, t=754s, t=12m34s, t=1h2m5s
LINK_TIME = re.compile(r"[?&#]t=(?:(\d+)h)?(?:(\d+)m)?(?:(\d+)s?)?(?:&|$)")
UNCLEAR = re.compile(r"\[unclear(?::[^\]]*)?\]", re.IGNORECASE)
INLINE_CODE = re.compile(r"(`+).*?\1")
FENCE = re.compile(r"^\s*(`{3,}|~{3,})")
HEADING = re.compile(r"^\s{0,3}#{1,6}(\s|$)")
SETEXT_UNDERLINE = re.compile(r"^\s{0,3}(=+|-+)\s*$")
RULE = re.compile(r"^\s*([-*_])(\s*\1){2,}\s*$")
TABLE_SEPARATOR = re.compile(r"^\s*\|?\s*:?-+:?\s*(\|\s*:?-+:?\s*)*\|?\s*$")
QUOTE_PREFIX = re.compile(r"^\s*(>\s?)+")
CALLOUT_HEADER = re.compile(r"^\[![\w-]+\][+-]?")
LIST_PREFIX = re.compile(r"^[\s>*+\-]*(\d+[.)])?\s*")
COMMENTS = {"<!--": "-->", "%%": "%%"}

# How far a timestamp may sit from a Transcript segment or Key frame. Citations are
# written to the second and segments can start a moment after the idea begins.
NEARBY_SECONDS = 5.0
IMAGE_EXTENSIONS = (".jpg", ".jpeg", ".png", ".gif", ".webp", ".svg", ".bmp")


class ProblemCode(StrEnum):
    """Stable codes, documented in docs/verify.md."""

    MISSING_CITATION = "missing_citation"
    TIMESTAMP_OUT_OF_RANGE = "timestamp_out_of_range"
    TIMESTAMP_NOT_NEAR_CONTENT = "timestamp_not_near_content"
    LINK_TIME_MISMATCH = "link_time_mismatch"
    UNKNOWN_FRAME = "unknown_frame"


@dataclass(frozen=True)
class Problem:
    line: int
    problem: ProblemCode
    message: str
    suggestion: str


@dataclass(frozen=True)
class _Bundle:
    duration: float
    segments: list[tuple[float, float]]
    frame_times: list[float]
    frame_names: frozenset[str]

    @classmethod
    def load(cls, directory: Path) -> _Bundle:
        manifest = _read_json(directory / "manifest.json")
        transcript = _read_json(directory / "transcript.json")
        try:
            frames = manifest.get("key_frames", {}).get("frames", [])
            return cls(
                duration=float(manifest["duration"]),
                segments=[(float(s["start"]), float(s["end"])) for s in transcript["segments"]],
                frame_times=[float(f["time"]) for f in frames],
                frame_names=frozenset(Path(f["file"]).name for f in frames),
            )
        except (KeyError, TypeError, ValueError, AttributeError):
            raise LectureNotesError(f"{directory} is not a valid Lecture bundle") from None

    def has_content_near(self, time: float) -> bool:
        near = NEARBY_SECONDS
        return any(start - near <= time <= end + near for start, end in self.segments) or any(
            abs(time - frame) <= near for frame in self.frame_times
        )


def verify(note: str, bundle_dir: Path) -> list[Problem]:
    """Problems in the Lecture note, in line order. Raises LectureNotesError if the
    bundle can't be read."""
    bundle = _Bundle.load(bundle_dir)
    problems: list[Problem] = []
    for line_number, text in _idea_lines(note):
        problems.extend(_check_timestamps(line_number, text, bundle))
        images = _embedded_images(text)
        unknown = [image for image in images if Path(image).name not in bundle.frame_names]
        problems.extend(
            Problem(
                line=line_number,
                problem=ProblemCode.UNKNOWN_FRAME,
                message=f"{image} is not a Key frame in the Lecture bundle",
                suggestion="embed a Key frame listed in manifest.json (frames/frame_<seconds>.jpg) "
                "or remove the image",
            )
            for image in unknown
        )
        cited = bool(TIMESTAMP.search(text)) or len(images) > len(unknown)
        if not cited and not unknown and not _only_unclear(text):
            problems.append(Problem(
                line=line_number,
                problem=ProblemCode.MISSING_CITATION,
                message=f"idea has no Citation: {text.strip()[:80]}",
                suggestion="end the line with the timestamp it comes from, e.g. [12:34], "
                "or embed the Key frame it shows; mark unreadable parts [unclear]",
            ))
    return problems


def _check_timestamps(line_number: int, text: str, bundle: _Bundle) -> Iterator[Problem]:
    for match in TIMESTAMP.finditer(text):
        hours, minutes, seconds, link = match.groups()
        time = int(hours or 0) * 3600 + int(minutes) * 60 + int(seconds)
        label = match.group(0).split("]")[0] + "]"
        link_time = _link_time(link or "")
        if link_time is not None and link_time != time:
            yield Problem(
                line=line_number,
                problem=ProblemCode.LINK_TIME_MISMATCH,
                message=f"{label} links to t={link_time} s but its label says {time} s",
                suggestion=f"make the link's t= match the label: t={time}",
            )
        if time > bundle.duration:
            yield Problem(
                line=line_number,
                problem=ProblemCode.TIMESTAMP_OUT_OF_RANGE,
                message=f"{label} is after the end of the Lecture "
                f"({format_timestamp(bundle.duration)})",
                suggestion="cite the timestamp where this is said or shown in the Transcript",
            )
        elif not bundle.has_content_near(time):
            yield Problem(
                line=line_number,
                problem=ProblemCode.TIMESTAMP_NOT_NEAR_CONTENT,
                message=f"{label} has no Transcript segment or Key frame within {NEARBY_SECONDS:g} s",
                suggestion="look the idea up in transcript.json and cite the start of its segment",
            )


def _link_time(link: str) -> int | None:
    """Seconds in a link's t= parameter, or None if it has none."""
    match = LINK_TIME.search(link)
    if match is None or not any(match.groups()):
        return None
    hours, minutes, seconds = (int(g or 0) for g in match.groups())
    return hours * 3600 + minutes * 60 + seconds


def _read_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        raise LectureNotesError(f"cannot read {path}; is this a Lecture bundle?") from None


def _only_unclear(text: str) -> bool:
    """The line is just an Unclear marker: it states nothing that would need a Citation."""
    if not UNCLEAR.search(text):
        return False
    rest = LIST_PREFIX.sub("", UNCLEAR.sub("", text))
    return not re.search(r"\w", rest)


def _embedded_images(text: str) -> list[str]:
    """Targets of `![alt](...)`, `<img src=...>` and image `![[...]]` embeds.
    A `![[...]]` without an image extension embeds a note, not an image."""
    wiki = [m.group(1).strip() for m in WIKI_EMBED.finditer(text)]
    images = [t for t in wiki if t.lower().endswith(IMAGE_EXTENSIONS)]
    images += [m.group(1).strip() for m in MARKDOWN_IMAGE.finditer(text)]
    images += [m.group(1).strip() for m in HTML_IMAGE.finditer(text)]
    return images


def _idea_lines(note: str) -> Iterator[tuple[int, str]]:
    """(line number, text without inline code) of every line that states an idea.

    Not ideas: frontmatter, fenced blocks (code, Mermaid), $$ math blocks, comments,
    headings (ATX and setext), callout headers, horizontal rules, table headers and
    separators, blank lines.
    """
    lines = note.splitlines()
    fence: str | None = None
    comment_end: str | None = None
    in_math = False
    start = 0
    if lines and lines[0].strip() == "---":
        end = next((i for i in range(1, len(lines)) if lines[i].strip() == "---"), None)
        if end is not None:
            start = end + 1
    for index in range(start, len(lines)):
        line = lines[index]
        stripped = line.strip()
        next_line = lines[index + 1] if index + 1 < len(lines) else ""
        if fence is not None:
            if re.fullmatch(re.escape(fence[0]) + f"{{{len(fence)},}}", stripped):
                fence = None
            continue
        if comment_end is not None:
            if stripped.endswith(comment_end):
                comment_end = None
            continue
        if match := FENCE.match(line):
            fence = match.group(1)
            continue
        if in_math:
            in_math = not stripped.endswith("$$")
            continue
        if stripped.startswith("$$"):
            in_math = not (len(stripped) >= 4 and stripped.endswith("$$"))
            continue
        opener = next((o for o in COMMENTS if stripped.startswith(o)), None)
        if opener is not None:
            closer = COMMENTS[opener]
            if not stripped[len(opener):].endswith(closer):
                comment_end = closer
            continue
        content = QUOTE_PREFIX.sub("", line).strip()
        if not content or CALLOUT_HEADER.match(content):
            continue
        if HEADING.match(line) or RULE.match(line) or SETEXT_UNDERLINE.match(line):
            continue
        if SETEXT_UNDERLINE.match(next_line):
            continue  # setext heading text
        if "|" in stripped and "|" in next_line and TABLE_SEPARATOR.match(next_line):
            continue  # table header
        if "|" in stripped and TABLE_SEPARATOR.match(line):
            continue
        yield index + 1, INLINE_CODE.sub("", line)
