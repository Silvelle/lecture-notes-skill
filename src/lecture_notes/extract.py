"""Source to Lecture bundle."""

from __future__ import annotations

import re
import sys
import tempfile
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

from lecture_notes import bundle, frames, hardware, media
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
from lecture_notes.hardware import DeviceReport, TranscriberChoice
from lecture_notes.transcriber import Transcriber, Transcription

TranscriberFactory = Callable[[TranscriberChoice], Transcriber]

# Transcript origins, best first.
HUMAN_SUBTITLES = "human_subtitles"
LOCAL_SPEECH_RECOGNITION = "local_speech_recognition"
AUTO_SUBTITLES = "auto_subtitles"


@dataclass(frozen=True)
class _Recognition:
    """How local speech recognition will run, if it does."""

    factory: TranscriberFactory
    choice: TranscriberChoice
    assume_yes: bool


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
    transcriber_factory: TranscriberFactory | None = None,
    downloader: Downloader | None = None,
    hardware_report: DeviceReport | None = None,
    model: str | None = None,
    device: str | None = None,
    assume_yes: bool = False,
    cookies_from_browser: str | None = None,
    language: str | None = None,
    allow_auto_subs: bool = False,
    with_key_frames: bool = True,
    min_frame_interval: float = frames.DEFAULT_MIN_INTERVAL,
) -> Path:
    """Turn a Source (URL or local file) into a Lecture bundle; return the bundle folder.
    Without `out_dir` the bundle goes to ./<title>."""
    choice = hardware.choose(hardware_report or hardware.probe(), model=model, device=device)
    recognition = _Recognition(
        factory=transcriber_factory or _default_transcriber, choice=choice, assume_yes=assume_yes
    )
    with tempfile.TemporaryDirectory() as tmp:
        workdir = Path(tmp)
        if is_url(source):
            url = normalise_url(source)
            downloader = downloader or _default_downloader(cookies_from_browser)
            info, fetched, blocked = _fetch_url(url, downloader, workdir)
            transcription, origin = _url_transcript(
                url, info, fetched, downloader, recognition, language, allow_auto_subs, workdir,
                local_recognition=transcriber_factory is not None or _whisper_installed(),
            )
            if transcription is None:
                assert blocked is not None  # with a video, speech recognition always runs
                raise LectureNotesError(blocked_message(url, blocked))
        else:
            fetched = _fetch_file(Path(source))
            assert fetched.video is not None
            transcription = _recognise(fetched, recognition, language, workdir)
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
    recognised = origin == LOCAL_SPEECH_RECOGNITION
    bundle.write(out_dir, source=fetched.source_entry, title=fetched.title,
                 channel=fetched.channel, duration=fetched.duration,
                 transcription=transcription, transcript_origin=origin,
                 hardware_tier=choice.tier if recognised else None,
                 compute_type=choice.compute_type if recognised else None,
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
    fetched: _Fetched,
    downloader: Downloader,
    recognition: _Recognition,
    language: str | None,
    allow_auto_subs: bool,
    workdir: Path,
    *,
    local_recognition: bool,
) -> tuple[Transcription | None, str]:
    """Human-written subtitles, else local speech recognition, else auto-generated
    subtitles (only when allowed or when local recognition is impossible)."""
    language = language or info.language
    human = pick_subtitles(info.subtitle_languages, language)
    if human:
        return _subtitles(url, downloader, human, automatic=False), HUMAN_SUBTITLES
    can_recognise = fetched.video is not None and local_recognition
    if can_recognise and not allow_auto_subs:
        return _recognise(fetched, recognition, language, workdir), LOCAL_SPEECH_RECOGNITION
    auto = pick_subtitles(info.auto_subtitle_languages, language)
    if auto:
        return _subtitles(url, downloader, auto, automatic=True), AUTO_SUBTITLES
    if can_recognise:  # --allow-auto-subs, but there are none
        return _recognise(fetched, recognition, language, workdir), LOCAL_SPEECH_RECOGNITION
    return None, ""


def _subtitles(url: str, downloader: Downloader, code: str, *, automatic: bool) -> Transcription:
    segments = downloader.fetch_subtitles(url, code, automatic=automatic)
    language = code.removesuffix("-orig").split("-")[0]
    return Transcription(language=language, segments=segments, model=None, device=None)


def _recognise(fetched: _Fetched, recognition: _Recognition, language: str | None,
               workdir: Path) -> Transcription:
    assert fetched.video is not None
    if recognition.factory is _default_transcriber and not _whisper_installed():
        from lecture_notes.whisper import WHISPER_MISSING

        raise LectureNotesError(WHISPER_MISSING)
    _confirm_heavy_work(recognition, fetched.duration)
    transcriber = recognition.factory(recognition.choice)
    wav = workdir / "audio.wav"
    media.extract_audio(fetched.video, wav)
    return transcriber.transcribe(wav, language)


def _confirm_heavy_work(recognition: _Recognition, audio_seconds: float) -> None:
    """Show the estimate; on CPU, ask before a long job (or demand --yes off a terminal)."""
    choice = recognition.choice
    estimate = choice.estimate_seconds(audio_seconds)
    print(f"Estimated transcription time: ~{_minutes(estimate)} for {_minutes(audio_seconds)} "
          f"of audio with {choice.describe()}", file=sys.stderr)
    if recognition.assume_yes or choice.device != "cpu":
        return
    if estimate <= hardware.CONFIRM_ABOVE_SECONDS:
        return
    if not sys.stdin.isatty():
        raise LectureNotesError(
            "this would keep the CPU busy for a long time; rerun with --yes to go ahead, "
            "or with --allow-auto-subs to use the site's subtitles instead"
        )
    print("Continue? [y/N] ", end="", file=sys.stderr, flush=True)
    if sys.stdin.readline().strip().lower() not in ("y", "yes"):
        raise LectureNotesError("stopped before transcription")


def _minutes(seconds: float) -> str:
    return f"{max(1, round(seconds / 60))} min"


def _whisper_installed() -> bool:
    try:
        import faster_whisper  # noqa: F401
    except ImportError:
        return False
    return True


def _folder_name(title: str) -> str:
    """A safe folder name from a Lecture title."""
    name = re.sub(r"[^\w.-]+", "-", title, flags=re.UNICODE).strip("-.")
    return name[:80] or "lecture"


def _default_transcriber(choice: TranscriberChoice) -> Transcriber:
    from lecture_notes.whisper import FasterWhisperTranscriber

    return FasterWhisperTranscriber(choice)


def _default_downloader(cookies_from_browser: str | None) -> Downloader:
    from lecture_notes.ytdlp import YtDlpDownloader

    return YtDlpDownloader(cookies_from_browser=cookies_from_browser)
