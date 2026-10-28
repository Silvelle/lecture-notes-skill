"""Source to Lecture bundle."""

from __future__ import annotations

import re
import tempfile
from pathlib import Path

from lecture_notes import bundle, frames, media
from lecture_notes.errors import LectureNotesError
from lecture_notes.sources import (
    Downloader,
    SourceBlocked,
    blocked_message,
    is_url,
    normalise_url,
)
from lecture_notes.transcriber import Transcriber


def extract(
    source: str,
    out_dir: Path | None = None,
    *,
    transcriber: Transcriber | None = None,
    downloader: Downloader | None = None,
    cookies_from_browser: str | None = None,
    language: str | None = None,
    with_key_frames: bool = True,
    min_frame_interval: float = frames.DEFAULT_MIN_INTERVAL,
) -> Path:
    """Turn a Source (URL or local file) into a Lecture bundle; return the bundle folder.
    Without `out_dir` the bundle goes to ./<title>."""
    with tempfile.TemporaryDirectory() as tmp:
        if is_url(source):
            url = normalise_url(source)
            downloader = downloader or _default_downloader(cookies_from_browser)
            try:
                info = downloader.info(url)
                out_dir = out_dir or Path(_folder_name(info.title))
                video = downloader.download_video(url, Path(tmp))
            except SourceBlocked as error:
                raise LectureNotesError(blocked_message(url, error)) from None
            source_entry = {"kind": "url", "url": info.url}
            title, channel = info.title, info.channel
        else:
            video = Path(source)
            if not video.is_file():
                raise LectureNotesError(f"{source}: no such file")
            out_dir = out_dir or Path(video.stem)
            source_entry = {"kind": "local_file", "path": str(video.resolve())}
            title, channel = video.stem, None

        duration = media.probe_duration(video)
        transcriber = transcriber or _default_transcriber()
        wav = Path(tmp) / "audio.wav"
        media.extract_audio(video, wav)
        transcription = transcriber.transcribe(wav, language)

        frames.remove_key_frames(out_dir)
        if not with_key_frames:
            key_frames = frames.SKIPPED
        elif not media.has_video(video):
            key_frames = frames.NO_VIDEO
        else:
            key_frames = frames.extract_key_frames(
                video, out_dir, duration=duration, min_interval=min_frame_interval
            )
    bundle.write(out_dir, source=source_entry, title=title, channel=channel, duration=duration,
                 transcription=transcription, language_overridden=language is not None,
                 key_frames=key_frames)
    return out_dir


def _folder_name(title: str) -> str:
    """A safe folder name from a Lecture title."""
    name = re.sub(r"[^\w.-]+", "-", title, flags=re.UNICODE).strip("-.")
    return name[:80] or "lecture"


def _default_transcriber() -> Transcriber:
    from lecture_notes.whisper import FasterWhisperTranscriber

    return FasterWhisperTranscriber()


def _default_downloader(cookies_from_browser: str | None) -> Downloader:
    from lecture_notes.ytdlp import YtDlpDownloader

    return YtDlpDownloader(cookies_from_browser=cookies_from_browser)
