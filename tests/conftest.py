from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import pytest

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
