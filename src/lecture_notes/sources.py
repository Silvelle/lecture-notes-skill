"""Sources: where a Lecture comes from (a URL any supported site serves, or a local file)."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Protocol
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from lecture_notes.errors import LectureNotesError
from lecture_notes.transcriber import Segment

# Query parameters that only say where to start playing; one Lecture is the whole video.
TIME_PARAMETERS = {"t", "start", "time_continue"}


@dataclass(frozen=True)
class LectureInfo:
    url: str  # canonical page URL
    title: str
    channel: str | None
    duration: float
    language: str | None
    subtitle_languages: tuple[str, ...] = ()  # human-written subtitle tracks
    auto_subtitle_languages: tuple[str, ...] = ()  # auto-generated (site speech recognition)


class SourceBlocked(LectureNotesError):
    """The site refused to serve the Lecture (bot check, sign-in, rate limit)."""


class Downloader(Protocol):
    def info(self, url: str) -> LectureInfo:
        """Metadata only; nothing large is downloaded. Raises SourceBlocked."""
        ...

    def download_video(self, url: str, directory: Path) -> Path:
        """Download the video into `directory` and return its path. Raises SourceBlocked."""
        ...

    def fetch_subtitles(self, url: str, language: str, *, automatic: bool) -> list[Segment]:
        """One subtitle track (a code from LectureInfo) as Transcript segments."""
        ...


def pick_subtitles(available: tuple[str, ...], language: str | None) -> str | None:
    """The track in `language` (or a regional variant, or an auto track's `-orig`
    original). With no known language, only an unambiguous single original track."""
    if language:
        for code in available:
            if code == language or code == f"{language}-orig":
                return code
        return next((c for c in available if c.split("-")[0] == language), None)
    originals = [c for c in available if c.endswith("-orig")]
    if len(originals) == 1:
        return originals[0]
    return available[0] if len(available) == 1 else None


def is_url(source: str) -> bool:
    return urlsplit(source).scheme in ("http", "https")


def normalise_url(url: str) -> str:
    """Drop start-time parameters; reject playlists, keep a video picked from one."""
    parts = urlsplit(url)
    query = [(k, v) for k, v in parse_qsl(parts.query, keep_blank_values=True)
             if k not in TIME_PARAMETERS]
    keys = {k for k, _ in query}
    names_a_video = "v" in keys or parts.netloc.endswith("youtu.be") or any(
        parts.path.startswith(prefix) for prefix in ("/shorts/", "/live/", "/embed/")
    )
    if "list" in keys:
        if not names_a_video:
            raise LectureNotesError(
                f"{url} is a playlist; pass the URL of one video (one Lecture per run)"
            )
        query = [(k, v) for k, v in query if k not in ("list", "index")]
    fragment = "" if parts.fragment.startswith("t=") else parts.fragment
    return urlunsplit(parts._replace(query=urlencode(query), fragment=fragment))


def blocked_message(url: str, error: SourceBlocked) -> str:
    return (
        f"{url} was blocked by the site: {error}\n"
        "  Ways out:\n"
        "  - pass --cookies-from-browser BROWSER[:PROFILE] to use a logged-in session; this risks\n"
        "    the account being flagged or banned, so prefer a secondary account\n"
        "  - download the video another way and pass the local file instead of the URL\n"
        "  - if only the video is blocked and subtitles are reachable, extract makes a\n"
        "    transcript-only bundle on its own (no Key frames)"
    )
