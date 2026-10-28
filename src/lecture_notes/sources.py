"""Sources: where a Lecture comes from (a URL any supported site serves, or a local file)."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Protocol
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from lecture_notes.errors import LectureNotesError

# Query parameters that only say where to start playing; one Lecture is the whole video.
TIME_PARAMETERS = {"t", "start", "time_continue"}


@dataclass(frozen=True)
class LectureInfo:
    url: str  # canonical page URL
    title: str
    channel: str | None
    duration: float
    language: str | None


class SourceBlocked(LectureNotesError):
    """The site refused to serve the Lecture (bot check, sign-in, rate limit)."""


class Downloader(Protocol):
    def info(self, url: str) -> LectureInfo:
        """Metadata only; nothing large is downloaded. Raises SourceBlocked."""
        ...

    def download_video(self, url: str, directory: Path) -> Path:
        """Download the video into `directory` and return its path. Raises SourceBlocked."""
        ...


def is_url(source: str) -> bool:
    return urlsplit(source).scheme in ("http", "https")


def normalise_url(url: str) -> str:
    """Drop start-time parameters; reject playlists, keep a video picked from one."""
    parts = urlsplit(url)
    query = [(k, v) for k, v in parse_qsl(parts.query, keep_blank_values=True)
             if k not in TIME_PARAMETERS]
    keys = {k for k, _ in query}
    if "list" in keys:
        if "v" not in keys:
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
