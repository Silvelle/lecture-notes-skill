"""`extract --plan`: what extract would do, without downloading or transcribing."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from lecture_notes.cli import main
from lecture_notes.transcriber import Segment
from tests.conftest import FakeDownloader, FakeTranscriber

URL = "https://www.youtube.com/watch?v=abc123"


def plan(capsys: pytest.CaptureFixture[str], *args: str, **injected: object) -> dict[str, object]:
    assert main(["extract", *args, "--plan"], **injected) == 0  # type: ignore[arg-type]
    result: dict[str, object] = json.loads(capsys.readouterr().out)
    return result


def test_plan_for_a_local_file(
    lecture_file: Path, tmp_path: Path, fake_transcriber: FakeTranscriber,
    capsys: pytest.CaptureFixture[str],
) -> None:
    result = plan(capsys, str(lecture_file), "-o", str(tmp_path / "b"),
                  transcriber_factory=fake_transcriber)

    assert result["title"] == "lecture"
    assert result["duration"] == pytest.approx(6.0, abs=0.2)
    assert result["transcript_origin"] == "local_speech_recognition"
    assert (result["model"], result["device"]) == ("small", "cpu")
    assert result["estimate_seconds"] == pytest.approx(2.4, abs=0.2)  # small on CPU: 0.4x
    assert result["needs_confirmation"] is False
    assert result["bundle"] == str(tmp_path / "b")
    assert fake_transcriber.calls == []
    assert not (tmp_path / "b").exists()


def test_plan_for_a_url_with_human_subtitles_downloads_nothing(
    tmp_path: Path, fake_downloader: FakeDownloader, fake_transcriber: FakeTranscriber,
    capsys: pytest.CaptureFixture[str],
) -> None:
    fake_downloader.human_subtitles = {"en": [Segment(0.0, 2.0, "Hello.")]}
    fake_downloader.video = None  # a download attempt would fail

    result = plan(capsys, URL, transcriber_factory=fake_transcriber, downloader=fake_downloader)

    assert result["title"] == "Python basics"
    assert result["transcript_origin"] == "human_subtitles"
    assert result["model"] is None and result["estimate_seconds"] == 0
    assert result["needs_confirmation"] is False
    assert result["bundle"] == "Python-basics"
    assert fake_downloader.subtitle_requests == []


def test_plan_flags_a_long_cpu_job(
    lecture_file: Path, tmp_path: Path, fake_transcriber: FakeTranscriber,
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.setattr("lecture_notes.hardware.CONFIRM_ABOVE_SECONDS", 1.0)

    result = plan(capsys, str(lecture_file), "-o", str(tmp_path / "b"), "--model", "large-v3",
                  transcriber_factory=fake_transcriber)

    assert result["needs_confirmation"] is True
