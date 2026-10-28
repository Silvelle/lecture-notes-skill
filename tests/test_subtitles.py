"""Subtitles first: which Transcript a URL Source gets (fake downloader, fake transcriber)."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

from lecture_notes.cli import main
from lecture_notes.sources import SourceBlocked
from lecture_notes.transcriber import Segment
from tests.conftest import FakeDownloader, FakeTranscriber, read_json

URL = "https://www.youtube.com/watch?v=abc123"
HUMAN = [Segment(start=0.0, end=2.0, text="Today: loops, written by a person.")]
AUTO = [Segment(start=0.0, end=2.0, text="today loops els print a")]


def extract(tmp_path: Path, downloader: FakeDownloader, *args: str,
            transcriber_factory: FakeTranscriber | None = None) -> tuple[int, Path]:
    bundle = tmp_path / "bundle"
    code = main(["extract", URL, "-o", str(bundle), *args],
                transcriber_factory=transcriber_factory, downloader=downloader)
    return code, bundle


def test_human_subtitles_win_and_whisper_is_skipped(
    tmp_path: Path, fake_downloader: FakeDownloader, fake_transcriber: FakeTranscriber
) -> None:
    fake_downloader.human_subtitles = {"en": HUMAN}
    fake_downloader.auto_subtitles = {"en": AUTO}

    code, bundle = extract(tmp_path, fake_downloader, transcriber_factory=fake_transcriber)

    manifest = read_json(bundle / "manifest.json")
    assert code == 0
    assert manifest["transcript_origin"] == "human_subtitles"
    assert manifest["model"] is None
    assert read_json(bundle / "transcript.json")["segments"][0]["text"] == HUMAN[0].text
    assert fake_transcriber.calls == []
    assert len(manifest["key_frames"]["frames"]) == 3


def test_human_subtitles_match_a_regional_variant_of_the_language(
    tmp_path: Path, fake_downloader: FakeDownloader, fake_transcriber: FakeTranscriber
) -> None:
    fake_downloader.human_subtitles = {"de": HUMAN, "en-US": HUMAN}

    extract(tmp_path, fake_downloader, transcriber_factory=fake_transcriber)

    assert fake_downloader.subtitle_requests == [("en-US", False)]


def test_only_auto_subtitles_and_a_transcriber_means_whisper(
    tmp_path: Path, fake_downloader: FakeDownloader, fake_transcriber: FakeTranscriber
) -> None:
    fake_downloader.auto_subtitles = {"en": AUTO}

    code, bundle = extract(tmp_path, fake_downloader, transcriber_factory=fake_transcriber)

    assert code == 0
    assert read_json(bundle / "manifest.json")["transcript_origin"] == "local_speech_recognition"
    assert fake_transcriber.calls
    assert fake_downloader.subtitle_requests == []


def test_allow_auto_subs_uses_them_and_marks_them(
    tmp_path: Path, fake_downloader: FakeDownloader, fake_transcriber: FakeTranscriber
) -> None:
    fake_downloader.auto_subtitles = {"en-orig": AUTO, "fr": AUTO}

    code, bundle = extract(tmp_path, fake_downloader, "--allow-auto-subs", transcriber_factory=fake_transcriber)

    manifest = read_json(bundle / "manifest.json")
    assert code == 0
    assert manifest["transcript_origin"] == "auto_subtitles"
    assert manifest["language"] == "en"
    assert fake_downloader.subtitle_requests == [("en-orig", True)]
    assert fake_transcriber.calls == []


def test_without_local_recognition_auto_subtitles_are_the_fallback(
    tmp_path: Path, fake_downloader: FakeDownloader, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setitem(sys.modules, "faster_whisper", None)  # no `whisper` extra
    fake_downloader.auto_subtitles = {"en": AUTO}

    code, bundle = extract(tmp_path, fake_downloader)

    assert code == 0
    assert read_json(bundle / "manifest.json")["transcript_origin"] == "auto_subtitles"


def test_blocked_video_with_subtitles_gives_a_transcript_only_bundle(
    tmp_path: Path, fake_downloader: FakeDownloader, fake_transcriber: FakeTranscriber
) -> None:
    fake_downloader.video_blocked = SourceBlocked("Sign in to confirm you're not a bot")
    fake_downloader.auto_subtitles = {"en": AUTO}

    code, bundle = extract(tmp_path, fake_downloader, transcriber_factory=fake_transcriber)

    manifest = read_json(bundle / "manifest.json")
    assert code == 0
    assert manifest["transcript_origin"] == "auto_subtitles"
    assert manifest["key_frames"] == {
        "status": "video_blocked", "min_interval": None, "frames": [], "ocr_languages": None,
    }
    assert manifest["duration"] == 6.0  # from the site's metadata
    assert not (bundle / "frames").exists()


def test_blocked_video_without_subtitles_is_the_blocked_error(
    tmp_path: Path, fake_downloader: FakeDownloader, fake_transcriber: FakeTranscriber,
    capsys: pytest.CaptureFixture[str],
) -> None:
    fake_downloader.video_blocked = SourceBlocked("Sign in to confirm you're not a bot")

    code, _ = extract(tmp_path, fake_downloader, transcriber_factory=fake_transcriber)

    assert code == 1
    assert "Ways out" in capsys.readouterr().err
