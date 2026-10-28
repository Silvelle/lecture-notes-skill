"""yt-dlp downloader: any URL yt-dlp supports (YouTube needs a JS runtime such as deno)."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

import yt_dlp
from yt_dlp.utils import DownloadError

from lecture_notes.errors import LectureNotesError
from lecture_notes.sources import LectureInfo, SourceBlocked

# Good enough to read code on screen, without fetching 4K.
VIDEO_FORMAT = "bv*[height<=1080]+ba/b[height<=1080]/b"
_BLOCKED = re.compile(
    r"not a bot|sign in to confirm|429|too many requests|http error 403", re.IGNORECASE
)


class _SilentLogger:
    """yt-dlp prints errors itself even when quiet; ours replace them."""

    def debug(self, message: str) -> None: ...
    def info(self, message: str) -> None: ...
    def warning(self, message: str) -> None: ...
    def error(self, message: str) -> None: ...


class YtDlpDownloader:
    def __init__(self, cookies_from_browser: str | None = None) -> None:
        self._params: dict[str, Any] = {
            "quiet": True,
            "no_warnings": True,
            "noprogress": True,
            "noplaylist": True,
            "logger": _SilentLogger(),
        }
        # Browser cookies are only read when the user asked for them.
        if cookies_from_browser:
            browser, _, profile = cookies_from_browser.partition(":")
            self._params["cookiesfrombrowser"] = (browser, profile or None, None, None)

    def info(self, url: str) -> LectureInfo:
        data = self._run(url, {}, download=False)
        return LectureInfo(
            url=data.get("webpage_url") or url,
            title=data.get("title") or url,
            channel=data.get("channel") or data.get("uploader"),
            duration=float(data.get("duration") or 0),
            language=data.get("language"),
        )

    def download_video(self, url: str, directory: Path) -> Path:
        options = {
            "format": VIDEO_FORMAT,
            "merge_output_format": "mp4",
            "outtmpl": str(directory / "video.%(ext)s"),
        }
        data = self._run(url, options, download=True)
        return Path(data["requested_downloads"][0]["filepath"])

    def _run(self, url: str, options: dict[str, Any], *, download: bool) -> dict[str, Any]:
        try:
            with yt_dlp.YoutubeDL({**self._params, **options}) as ydl:
                data = ydl.extract_info(url, download=download)
        except DownloadError as error:
            message = re.sub(r"^ERROR:\s*", "", str(error)).splitlines()[0].split(". ")[0]
            if _BLOCKED.search(message):
                raise SourceBlocked(message) from None
            raise LectureNotesError(f"yt-dlp could not get {url}: {message}") from None
        if not isinstance(data, dict):
            raise LectureNotesError(f"yt-dlp returned nothing for {url}")
        return data
