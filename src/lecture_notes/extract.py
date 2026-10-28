"""Source to Lecture bundle."""

from __future__ import annotations

import re
import sys
import tempfile
from collections.abc import Callable
from dataclasses import dataclass, replace
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
from lecture_notes.transcriber import Transcriber, Transcription, TranscriptOrigin

TranscriberFactory = Callable[[TranscriberChoice], Transcriber]


@dataclass(frozen=True)
class _Recognition:
    """How local speech recognition will run, if it does."""

    factory: TranscriberFactory | None  # None: the installed backend for the choice
    report: DeviceReport
    model: str | None
    device: str | None
    backend: str | None
    assume_yes: bool

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
            info, fetched, blocked = _fetch_url(
                url, downloader, workdir, with_key_frames=with_key_frames, language=language
            )
            transcription = _url_transcript(
                url, info, fetched, downloader, recognition, language, allow_auto_subs, workdir,
            )
            if transcription is None:
                assert blocked is not None  # with a video, speech recognition always runs
                raise LectureNotesError(blocked_message(url, blocked))
        else:
            fetched = _fetch_file(Path(source))
            assert fetched.video is not None
            transcription = _recognise(fetched, recognition, language, workdir)

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
    bundle.write(out_dir, source=fetched.source_entry, title=fetched.title,
                 channel=fetched.channel, duration=fetched.duration,
                 transcription=transcription, language_overridden=language is not None, key_frames=key_frames)
    return out_dir


@dataclass(frozen=True)
class Plan:
    """What `extract` would do, found without downloading or transcribing anything."""

    title: str
    source: dict[str, str]
    duration: float
    language: str | None
    transcript_origin: TranscriptOrigin | None  # None: no Transcript is possible
    model: str | None
    device: str | None
    estimate_seconds: float  # transcription only; 0 for subtitles
    needs_confirmation: bool  # a long CPU job: extract stops unless --yes
    key_frames: bool
    bundle: str


def plan(
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
) -> Plan:
    report = hardware_report or hardware.probe()
    can_recognise = transcriber_factory is not None or bool(report.backends)
    if is_url(source):
        url = normalise_url(source)
        downloader = downloader or _default_downloader(cookies_from_browser)
        try:
            info = downloader.info(url)
        except SourceBlocked as error:
            raise LectureNotesError(blocked_message(url, error)) from None
        origin, _ = _transcript_route(info, language, can_recognise=can_recognise,
                                      allow_auto_subs=allow_auto_subs)
        title, duration, language = info.title, info.duration, language or info.language
        source_entry = {"kind": "url", "url": info.url}
    else:
        fetched = _fetch_file(Path(source))
        origin = TranscriptOrigin.LOCAL_SPEECH_RECOGNITION if can_recognise else None
        title, duration, source_entry = fetched.title, fetched.duration, fetched.source_entry
    recognised = origin is TranscriptOrigin.LOCAL_SPEECH_RECOGNITION
    choice = hardware.choose(report, model=model, device=device, backend=backend,
                             language=language) if recognised else None
    estimate = choice.estimate_seconds(duration) if choice else 0.0
    return Plan(
        title=title, source=source_entry, duration=round(duration, 3), language=language,
        transcript_origin=origin,
        model=choice.model if choice else None, device=choice.device if choice else None,
        estimate_seconds=round(estimate, 1),
        needs_confirmation=choice is not None and _needs_confirmation(choice, estimate, assume_yes),
        key_frames=with_key_frames,
        bundle=str(out_dir or Path(_folder_name(title))),
    )


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
    url: str, downloader: Downloader, workdir: Path, *, with_key_frames: bool,
    language: str | None,
) -> tuple[LectureInfo, _Fetched, SourceBlocked | None]:
    """Metadata plus the video, unless neither Key frames nor speech recognition need it.
    A blocked video is not fatal while subtitles may exist."""
    try:
        info = downloader.info(url)
    except SourceBlocked as error:
        raise LectureNotesError(blocked_message(url, error)) from None
    has_human_subtitles = pick_subtitles(info.subtitle_languages, language or info.language)
    video: Path | None = None
    blocked: SourceBlocked | None = None
    if with_key_frames or not has_human_subtitles:
        try:
            video = downloader.download_video(url, workdir)
        except SourceBlocked as error:
            blocked = error
    fetched = _Fetched(
        source_entry={"kind": "url", "url": info.url},
        title=info.title,
        channel=info.channel,
        video=video,
        duration=media.probe_duration(video) if video else info.duration,
    )
    return info, fetched, blocked


def _transcript_route(
    info: LectureInfo, language: str | None, *, can_recognise: bool, allow_auto_subs: bool
) -> tuple[TranscriptOrigin | None, str | None]:
    """Where a URL Source's Transcript comes from, and which subtitle track if any:
    human-written subtitles, else local speech recognition, else auto-generated
    subtitles (only when allowed or when local recognition is impossible)."""
    language = language or info.language
    human = pick_subtitles(info.subtitle_languages, language)
    if human:
        return TranscriptOrigin.HUMAN_SUBTITLES, human
    if can_recognise and not allow_auto_subs:
        return TranscriptOrigin.LOCAL_SPEECH_RECOGNITION, None
    auto = pick_subtitles(info.auto_subtitle_languages, language)
    if auto:
        return TranscriptOrigin.AUTO_SUBTITLES, auto
    if can_recognise:  # --allow-auto-subs, but there are none
        return TranscriptOrigin.LOCAL_SPEECH_RECOGNITION, None
    return None, None


def _url_transcript(
    url: str,
    info: LectureInfo,
    fetched: _Fetched,
    downloader: Downloader,
    recognition: _Recognition,
    language: str | None,
    allow_auto_subs: bool,
    workdir: Path,
) -> Transcription | None:
    origin, track = _transcript_route(
        info, language, can_recognise=fetched.video is not None and recognition.available,
        allow_auto_subs=allow_auto_subs,
    )
    if origin is TranscriptOrigin.LOCAL_SPEECH_RECOGNITION:
        return _recognise(fetched, recognition, language or info.language, workdir)
    if track is not None:
        automatic = origin is TranscriptOrigin.AUTO_SUBTITLES
        return _subtitles(url, downloader, track, automatic=automatic)
    return None


def _subtitles(url: str, downloader: Downloader, code: str, *, automatic: bool) -> Transcription:
    segments = downloader.fetch_subtitles(url, code, automatic=automatic)
    language = code.removesuffix("-orig").split("-")[0]
    origin = TranscriptOrigin.AUTO_SUBTITLES if automatic else TranscriptOrigin.HUMAN_SUBTITLES
    return Transcription(language=language, segments=segments, model=None, device=None,
                         origin=origin)


def _recognise(fetched: _Fetched, recognition: _Recognition, language: str | None,
               workdir: Path) -> Transcription:
    assert fetched.video is not None
    choice = hardware.choose(recognition.report, model=recognition.model,
                             device=recognition.device, backend=recognition.backend,
                             language=language)
    if recognition.factory is None and choice.backend not in recognition.report.backends:
        raise LectureNotesError(hardware.BACKENDS[choice.backend].install_hint(choice.backend))
    _confirm_heavy_work(choice, recognition.assume_yes, fetched.duration,
                        url_source=fetched.source_entry["kind"] == "url")
    transcriber = (recognition.factory or _default_transcriber)(choice)
    wav = workdir / "audio.wav"
    media.extract_audio(fetched.video, wav)
    return replace(transcriber.transcribe(wav, language), choice=choice)


def _confirm_heavy_work(choice: TranscriberChoice, assume_yes: bool, audio_seconds: float,
                        *, url_source: bool) -> None:
    """Show the estimate; on CPU, ask before a long job (or demand --yes off a terminal)."""
    estimate = choice.estimate_seconds(audio_seconds)
    print(f"Estimated transcription time: ~{_duration(estimate)} for {_duration(audio_seconds)} "
          f"of audio with {choice.describe()}", file=sys.stderr)
    if not _needs_confirmation(choice, estimate, assume_yes):
        return
    if not sys.stdin.isatty():
        alternative = (", or with --allow-auto-subs to use the site's subtitles instead"
                       if url_source else "")
        raise LectureNotesError(
            f"this would keep the CPU busy for a long time; rerun with --yes to go ahead{alternative}"
        )
    print("Continue? [y/N] ", end="", file=sys.stderr, flush=True)
    if sys.stdin.readline().strip().lower() not in ("y", "yes"):
        raise LectureNotesError("stopped before transcription")


def _needs_confirmation(choice: TranscriberChoice, estimate: float, assume_yes: bool) -> bool:
    """A long transcription on CPU, not yet agreed to."""
    return not assume_yes and choice.device == "cpu" and estimate > hardware.CONFIRM_ABOVE_SECONDS


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
