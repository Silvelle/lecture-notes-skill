"""Opt-in: real faster-whisper on a fixture Lecture with synthesised speech (`pytest -m slow`)."""

from __future__ import annotations

from pathlib import Path

import pytest

from lecture_notes.cli import main
from tests.conftest import read_json
from tests.fixture_lecture import has_tts, make_lecture

pytestmark = [
    pytest.mark.slow,
    pytest.mark.skipif(not has_tts(), reason="needs espeak-ng to synthesise the speech track"),
]


def test_faster_whisper_transcribes_the_fixture_with_timestamps(tmp_path: Path) -> None:
    lecture = make_lecture(tmp_path / "fixture", speech=True)
    bundle = tmp_path / "bundle"

    assert main(["extract", str(lecture), "-o", str(bundle), "--lang", "en"]) == 0

    manifest = read_json(bundle / "manifest.json")
    segments = read_json(bundle / "transcript.json")["segments"]
    assert manifest["transcript_origin"] == "local_speech_recognition"
    assert manifest["model"].startswith("faster-whisper/")
    assert segments, "expected speech to be recognised"
    assert all(s["text"].strip() for s in segments)
    for s in segments:
        assert 0.0 <= s["start"] < s["end"] <= manifest["duration"] + 0.5
    starts = [s["start"] for s in segments]
    assert starts == sorted(starts)
    text = " ".join(s["text"] for s in segments).lower()
    assert "print" in text and "equals" in text
    # the second slide's sentence is spoken after the first slide (>= 2 s in)
    assert any("equals" in s["text"].lower() and s["start"] >= 1.5 for s in segments)
