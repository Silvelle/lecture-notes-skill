"""Source to Lecture bundle."""

from __future__ import annotations

import re
import sys
import tempfile
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

from lecture_notes import bundle, frames, hardware, media, ocr
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

BACKEND_MISSING = {
    hardware.FASTER_WHISPER: "speech recognition needs faster-whisper; "
    "install it with: pip install 'lecture-notes[whisper]'",
    hardware.ONNX_ASR: "the onnx-asr backend (GigaAM for Russian) is not installed; "
    "install it with: pip install 'lecture-notes[ru]'",
}

# Transcript origins, best first.
HUMAN_SUBTITLES = "human_subtitles"
LOCAL_SPEECH_RECOGNITION = "local_speech_recognition"
AUTO_SUBTITLES = "auto_subtitles"


@dataclass
class _Recognition:
    """How local speech recognition will run, if it does; `used` records the choice."""

    factory: TranscriberFactory | None  # None: the installed backend for the choice
    report: DeviceReport
    model: str | None
    device: str | None
    backend: str | None
    assume_yes: bool
    used: TranscriberChoice | None = None

    @property
    def available(self) -> bool:
        return self.factory is not None or bool(self.report.backends)


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
    backend: str | None = None,
    assume_yes: bool = False,
    cookies_from_browser: str | None = None,
    language: str | None = None,
    allow_auto_subs: bool = False,
    with_key_frames: bool = True,
    min_frame_interval: float = frames.DEFAULT_MIN_INTERVAL,
) -> Path:
    """Turn a Source (URL or local file) into a Lecture bundle; return the bundle folder.
    Without `out_dir` the bundle goes to ./<title>."""
    recognition = _Recognition(
        factory=transcriber_factory, report=hardware_report or hardware.probe(),
        model=model, device=device, backend=backend, assume_yes=assume_yes,
    )
    with tempfile.TemporaryDirectory() as tmp:
        workdir = Path(tmp)
        if is_url(source):
            url = normalise_url(source)
            downloader = downloader or _default_downloader(cookies_from_browser)
            info, fetched, blocked = _fetch_url(url, downloader, workdir)
            transcription, origin = _url_transcript(
                url, info, fetched, downloader, recognition, language, allow_auto_subs, workdir,
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
            key_frames = ocr.add_text(key_frames, out_dir, transcription.language)
    used = recognition.used
    bundle.write(out_dir, source=fetched.source_entry, title=fetched.title,
                 channel=fetched.channel, duration=fetched.duration,
                 transcription=transcription, transcript_origin=origin,
                 backend=used.backend if used else None,
                 hardware_tier=used.tier if used else None,
                 compute_type=used.compute_type if used else None,
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
) -> tuple[Transcription | None, str]:
    """Human-written subtitles, else local speech recognition, else auto-generated
    subtitles (only when allowed or when local recognition is impossible)."""
    language = language or info.language
    human = pick_subtitles(info.subtitle_languages, language)
    if human:
        return _subtitles(url, downloader, human, automatic=False), HUMAN_SUBTITLES
    can_recognise = fetched.video is not None and recognition.available
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
    choice = hardware.choose(recognition.report, model=recognition.model,
                             device=recognition.device, backend=recognition.backend,
                             language=language)
    if recognition.factory is None and choice.backend not in recognition.report.backends:
        raise LectureNotesError(BACKEND_MISSING.get(choice.backend, f"unknown backend {choice.backend}"))
    _confirm_heavy_work(choice, recognition.assume_yes, fetched.duration)
    transcriber = (recognition.factory or _default_transcriber)(choice)
    recognition.used = choice
    wav = workdir / "audio.wav"
    media.extract_audio(fetched.video, wav)
    return transcriber.transcribe(wav, language)


def _confirm_heavy_work(choice: TranscriberChoice, assume_yes: bool, audio_seconds: float) -> None:
    """Show the estimate; on CPU, ask before a long job (or demand --yes off a terminal)."""
    estimate = choice.estimate_seconds(audio_seconds)
    print(f"Estimated transcription time: ~{_duration(estimate)} for {_duration(audio_seconds)} "
          f"of audio with {choice.describe()}", file=sys.stderr)
    if assume_yes or choice.device != "cpu":
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


def _duration(seconds: float) -> str:
    if seconds < 60:
        return f"{round(seconds)} s"
    if seconds < 3600:
        return f"{round(seconds / 60)} min"
    return f"{seconds / 3600:.1f} h"


def _folder_name(title: str) -> str:
    """A safe folder name from a Lecture title."""
    name = re.sub(r"[^\w.-]+", "-", title, flags=re.UNICODE).strip("-.")
    return name[:80] or "lecture"


def _default_transcriber(choice: TranscriberChoice) -> Transcriber:
    if choice.backend == hardware.ONNX_ASR:
        from lecture_notes.onnx import OnnxAsrTranscriber

        return OnnxAsrTranscriber(choice)
    from lecture_notes.whisper import FasterWhisperTranscriber

    return FasterWhisperTranscriber(choice)


def _default_downloader(cookies_from_browser: str | None) -> Downloader:
    from lecture_notes.ytdlp import YtDlpDownloader

    return YtDlpDownloader(cookies_from_browser=cookies_from_browser)
