"""Source to Lecture bundle."""

from __future__ import annotations

import re
import tempfile
from dataclasses import dataclass
from pathlib import Path

from lecture_notes import bundle, frames, media
from lecture_notes.errors import LectureNotesError
from lecture_notes.sources import (
    Downloader,
    LectureInfo,
    SourceBlocked,
    blocked_message,
    is_url,
    normalise_url,
    pick_subtitles,
)
from lecture_notes.transcriber import Transcriber, Transcription

# Transcript origins, best first.
HUMAN_SUBTITLES = "human_subtitles"
LOCAL_SPEECH_RECOGNITION = "local_speech_recognition"
AUTO_SUBTITLES = "auto_subtitles"


@dataclass(frozen=True)
class _Fetched:
    """A Source, ready for the pipeline."""

    source_entry: dict[str, str]
    title: str
    channel: str | None
    video: Path | None  # None: the site blocked the video download
    duration: float


def extract(
    source: str,
    out_dir: Path | None = None,
    *,
    transcriber: Transcriber | None = None,
    downloader: Downloader | None = None,
    cookies_from_browser: str | None = None,
    language: str | None = None,
    allow_auto_subs: bool = False,
    with_key_frames: bool = True,
    min_frame_interval: float = frames.DEFAULT_MIN_INTERVAL,
) -> Path:
    """Turn a Source (URL or local file) into a Lecture bundle; return the bundle folder.
    Without `out_dir` the bundle goes to ./<title>."""
    with tempfile.TemporaryDirectory() as tmp:
        workdir = Path(tmp)
        if is_url(source):
            url = normalise_url(source)
            downloader = downloader or _default_downloader(cookies_from_browser)
            info, fetched, blocked = _fetch_url(url, downloader, workdir)
            transcription, origin = _url_transcript(
                url, info, fetched.video, downloader, transcriber, language,
                allow_auto_subs, workdir,
            )
            if transcription is None:
                assert blocked is not None  # with a video, speech recognition always runs
                raise LectureNotesError(blocked_message(url, blocked))
        else:
            fetched = _fetch_file(Path(source))
            assert fetched.video is not None
            transcription = _recognise(fetched.video, transcriber or _default_transcriber(),
                                       language, workdir)
            origin = LOCAL_SPEECH_RECOGNITION

        out_dir = out_dir or Path(_folder_name(fetched.title))
        frames.remove_key_frames(out_dir)
        if not with_key_frames:
            key_frames = frames.SKIPPED
        elif fetched.video is None:
            key_frames = frames.VIDEO_BLOCKED
        elif not media.has_video(fetched.video):
            key_frames = frames.NO_VIDEO
        else:
            key_frames = frames.extract_key_frames(
                fetched.video, out_dir, duration=fetched.duration, min_interval=min_frame_interval
            )
    bundle.write(out_dir, source=fetched.source_entry, title=fetched.title,
                 channel=fetched.channel, duration=fetched.duration,
                 transcription=transcription, transcript_origin=origin,
                 language_overridden=language is not None, key_frames=key_frames)
    return out_dir


def _fetch_file(path: Path) -> _Fetched:
    if not path.is_file():
        raise LectureNotesError(f"{path}: no such file")
    return _Fetched(
        source_entry={"kind": "local_file", "path": str(path.resolve())},
        title=path.stem,
        channel=None,
        video=path,
        duration=media.probe_duration(path),
    )


def _fetch_url(
    url: str, downloader: Downloader, workdir: Path
) -> tuple[LectureInfo, _Fetched, SourceBlocked | None]:
    """Metadata plus the video; a blocked video is not fatal while subtitles may exist."""
    try:
        info = downloader.info(url)
    except SourceBlocked as error:
        raise LectureNotesError(blocked_message(url, error)) from None
    video: Path | None
    blocked: SourceBlocked | None = None
    try:
        video = downloader.download_video(url, workdir)
    except SourceBlocked as error:
        video, blocked = None, error
    fetched = _Fetched(
        source_entry={"kind": "url", "url": info.url},
        title=info.title,
        channel=info.channel,
        video=video,
        duration=media.probe_duration(video) if video else info.duration,
    )
    return info, fetched, blocked


def _url_transcript(
    url: str,
    info: LectureInfo,
    video: Path | None,
    downloader: Downloader,
    transcriber: Transcriber | None,
    language: str | None,
    allow_auto_subs: bool,
    workdir: Path,
) -> tuple[Transcription | None, str]:
    """Human-written subtitles, else local speech recognition, else auto-generated
    subtitles (only when allowed or when local recognition is impossible)."""
    language = language or info.language
    human = pick_subtitles(info.subtitle_languages, language)
    if human:
        return _subtitles(url, downloader, human, automatic=False), HUMAN_SUBTITLES

    recogniser = None
    if video is not None and not allow_auto_subs:
        recogniser = transcriber or _available_transcriber()
    if recogniser is not None and video is not None:
        return _recognise(video, recogniser, language, workdir), LOCAL_SPEECH_RECOGNITION

    auto = pick_subtitles(info.auto_subtitle_languages, language)
    if auto:
        return _subtitles(url, downloader, auto, automatic=True), AUTO_SUBTITLES
    if video is not None:  # --allow-auto-subs, but there are none
        recogniser = transcriber or _default_transcriber()
        return _recognise(video, recogniser, language, workdir), LOCAL_SPEECH_RECOGNITION
    return None, ""


def _subtitles(url: str, downloader: Downloader, code: str, *, automatic: bool) -> Transcription:
    segments = downloader.fetch_subtitles(url, code, automatic=automatic)
    language = code.removesuffix("-orig").split("-")[0]
    return Transcription(language=language, segments=segments, model=None, device=None)


def _recognise(video: Path, transcriber: Transcriber, language: str | None,
               workdir: Path) -> Transcription:
    wav = workdir / "audio.wav"
    media.extract_audio(video, wav)
    return transcriber.transcribe(wav, language)


def _folder_name(title: str) -> str:
    """A safe folder name from a Lecture title."""
    name = re.sub(r"[^\w.-]+", "-", title, flags=re.UNICODE).strip("-.")
    return name[:80] or "lecture"


def _available_transcriber() -> Transcriber | None:
    """The default local recogniser, or None when its extra isn't installed."""
    try:
        return _default_transcriber()
    except LectureNotesError:
        return None


def _default_transcriber() -> Transcriber:
    from lecture_notes.whisper import FasterWhisperTranscriber

    return FasterWhisperTranscriber()


def _default_downloader(cookies_from_browser: str | None) -> Downloader:
    from lecture_notes.ytdlp import YtDlpDownloader

    return YtDlpDownloader(cookies_from_browser=cookies_from_browser)
