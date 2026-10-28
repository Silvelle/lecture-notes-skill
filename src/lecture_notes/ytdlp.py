"""yt-dlp downloader: any URL yt-dlp supports (YouTube needs a JS runtime such as deno)."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

import yt_dlp
from yt_dlp.utils import DownloadError

from lecture_notes.errors import LectureNotesError
from lecture_notes.sources import LectureInfo, SourceBlocked
from lecture_notes.transcriber import Segment

# Good enough to read code on screen, without fetching 4K.
VIDEO_FORMAT = "bv*[height<=1080]+ba/b[height<=1080]/b"
_CUE_TIME = re.compile(r"^(\S+)\s+-->\s+(\S+)")
_INLINE_TAG = re.compile(r"<[^>]+>")
NOT_SUBTITLES = {"live_chat", "rechat"}
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
        self._infos: dict[str, dict[str, Any]] = {}
        # Browser cookies are only read when the user asked for them.
        if cookies_from_browser:
            browser, _, profile = cookies_from_browser.partition(":")
            self._params["cookiesfrombrowser"] = (browser, profile or None, None, None)

    def info(self, url: str) -> LectureInfo:
        data = self._run(url, {}, download=False)
        self._infos[url] = data
        return LectureInfo(
            url=data.get("webpage_url") or url,
            title=data.get("title") or url,
            channel=data.get("channel") or data.get("uploader"),
            duration=float(data.get("duration") or 0),
            language=data.get("language"),
            subtitle_languages=_tracks(data.get("subtitles")),
            auto_subtitle_languages=_tracks(data.get("automatic_captions")),
        )

    def fetch_subtitles(self, url: str, language: str, *, automatic: bool) -> list[Segment]:
        data = self._infos.get(url) or self._run(url, {}, download=False)
        tracks = data.get("automatic_captions" if automatic else "subtitles") or {}
        vtt = next((t["url"] for t in tracks.get(language, []) if t.get("ext") == "vtt"), None)
        if vtt is None:
            raise LectureNotesError(f"no WebVTT subtitles in {language} for {url}")
        try:
            with yt_dlp.YoutubeDL(self._params) as ydl:
                text = ydl.urlopen(vtt).read().decode("utf-8")
        except DownloadError as error:
            raise SourceBlocked(str(error).splitlines()[0]) from None
        return parse_vtt(text)

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


def _tracks(tracks: dict[str, Any] | None) -> tuple[str, ...]:
    return tuple(code for code in (tracks or {}) if code not in NOT_SUBTITLES)


def parse_vtt(text: str) -> list[Segment]:
    """WebVTT cues as segments. Drops YouTube's word-timing tags, the lines its auto
    captions repeat from the previous cue, and its 10 ms transition cues."""
    segments: list[Segment] = []
    previous_lines: list[str] = []
    for block in re.split(r"\n\s*\n", text.replace("\r\n", "\n")):
        lines = block.strip().splitlines()
        timing = next((i for i, line in enumerate(lines) if _CUE_TIME.match(line)), None)
        if timing is None:
            continue
        match = _CUE_TIME.match(lines[timing])
        assert match is not None
        start, end = _seconds(match.group(1)), _seconds(match.group(2))
        cue_lines = [_INLINE_TAG.sub("", line).strip() for line in lines[timing + 1:]]
        cue_lines = [line for line in cue_lines if line]
        new_lines = [line for line in cue_lines if line not in previous_lines]
        previous_lines = cue_lines
        if end - start < 0.05 or not new_lines:
            continue
        segments.append(Segment(start=start, end=end, text=" ".join(new_lines)))
    return segments


def _seconds(stamp: str) -> float:
    parts = [float(p) for p in stamp.replace(",", ".").split(":")]
    while len(parts) < 3:
        parts.insert(0, 0.0)
    hours, minutes, seconds = parts
    return round(hours * 3600 + minutes * 60 + seconds, 3)
