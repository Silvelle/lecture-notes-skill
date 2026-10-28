from __future__ import annotations

import json
import shutil
from dataclasses import dataclass, field, replace
from pathlib import Path
from typing import Any

import pytest

from lecture_notes.sources import LectureInfo, SourceBlocked
from lecture_notes.transcriber import Segment, Transcription
from tests.fixture_lecture import make_lecture


@pytest.fixture(scope="session")
def lecture_file(tmp_path_factory: pytest.TempPathFactory) -> Path:
    """A ~6 s fixture Lecture with a tone track (fake-transcriber tests need no speech)."""
    return make_lecture(tmp_path_factory.mktemp("fixture"), speech=False)


@dataclass
class FakeTranscriber:
    """In-memory transcriber: returns canned segments, records what it was asked."""

    segments: list[Segment]
    detected_language: str = "en"
    calls: list[tuple[Path, str | None]] = field(default_factory=list)

    def transcribe(self, audio: Path, language: str | None) -> Transcription:
        assert audio.is_file(), "transcriber must receive an extracted audio file"
        self.calls.append((audio, language))
        return Transcription(
            language=language or self.detected_language,
            segments=self.segments,
            model="fake-model",
            device="cpu",
        )


@pytest.fixture
def fake_transcriber() -> FakeTranscriber:
    return FakeTranscriber(
        segments=[
            Segment(start=0.0, end=1.8, text="First we assign one to a and print it."),
            Segment(start=2.0, end=3.9, text="Then we check whether a equals one."),
            Segment(start=4.0, end=5.9, text='els Принт А из нот единица print("a is not 1")'),
        ]
    )


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


@dataclass
class FakeDownloader:
    """In-memory downloader: serves a fixture Lecture as if it came from a URL."""

    video: Path | None
    info_result: LectureInfo = field(
        default_factory=lambda: LectureInfo(
            url="https://www.youtube.com/watch?v=abc123",
            title="Python basics",
            channel="MEPhI",
            duration=6.0,
            language="en",
        )
    )
    blocked: SourceBlocked | None = None
    video_blocked: SourceBlocked | None = None
    human_subtitles: dict[str, list[Segment]] = field(default_factory=dict)
    auto_subtitles: dict[str, list[Segment]] = field(default_factory=dict)
    requested: list[str] = field(default_factory=list)
    subtitle_requests: list[tuple[str, bool]] = field(default_factory=list)

    def info(self, url: str) -> LectureInfo:
        self.requested.append(url)
        if self.blocked:
            raise self.blocked
        return replace(
            self.info_result,
            subtitle_languages=tuple(self.human_subtitles),
            auto_subtitle_languages=tuple(self.auto_subtitles),
        )

    def fetch_subtitles(self, url: str, language: str, *, automatic: bool) -> list[Segment]:
        self.subtitle_requests.append((language, automatic))
        return (self.auto_subtitles if automatic else self.human_subtitles)[language]

    def download_video(self, url: str, directory: Path) -> Path:
        if self.blocked or self.video_blocked:
            raise self.blocked or self.video_blocked  # type: ignore[misc]
        assert self.video is not None
        target = directory / "video.mp4"
        shutil.copy(self.video, target)
        return target


@pytest.fixture
def fake_downloader(lecture_file: Path) -> FakeDownloader:
    return FakeDownloader(video=lecture_file)
