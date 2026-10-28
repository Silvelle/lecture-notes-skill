"""Seam 1: `lecture-notes extract` on a local file, observed through the Lecture bundle."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

from lecture_notes.cli import main
from lecture_notes.transcriber import Segment
from tests.conftest import FakeTranscriber, read_json


def test_extract_writes_transcript_and_manifest(
    lecture_file: Path, tmp_path: Path, fake_transcriber: FakeTranscriber
) -> None:
    bundle = tmp_path / "bundle"

    exit_code = main(["extract", str(lecture_file), "-o", str(bundle)], transcriber_factory=fake_transcriber)

    assert exit_code == 0
    assert (bundle / "manifest.json").is_file()
    assert (bundle / "transcript.json").is_file()
    assert (bundle / "transcript.md").is_file()


def test_manifest_records_source_duration_language_and_origin(
    lecture_file: Path, tmp_path: Path, fake_transcriber: FakeTranscriber
) -> None:
    bundle = tmp_path / "bundle"
    fake_transcriber.detected_language = "ru"

    main(["extract", str(lecture_file), "-o", str(bundle)], transcriber_factory=fake_transcriber)

    manifest = read_json(bundle / "manifest.json")
    assert manifest["schema_version"] == 1
    assert manifest["source"] == {"kind": "local_file", "path": str(lecture_file.resolve())}
    assert manifest["title"] == "lecture"
    assert manifest["duration"] == pytest.approx(6.0, abs=0.2)  # 3 slides x 2 s
    assert manifest["language"] == "ru"
    assert manifest["language_origin"] == "detected"
    assert manifest["transcript_origin"] == "local_speech_recognition"
    assert manifest["model"] == "small"  # chosen for the (test) CPU-only machine
    assert manifest["device"] == "cpu"
    assert manifest["hardware_tier"] == "cpu"
    assert manifest["tool_version"] == "0.1.0"
    assert fake_transcriber.calls[0][1] is None, "no --lang means the transcriber detects"


def test_lang_option_overrides_detection_and_is_recorded(
    lecture_file: Path, tmp_path: Path, fake_transcriber: FakeTranscriber
) -> None:
    bundle = tmp_path / "bundle"
    fake_transcriber.detected_language = "en"

    main(["extract", str(lecture_file), "-o", str(bundle), "--lang", "ru"], transcriber_factory=fake_transcriber)

    assert fake_transcriber.calls[0][1] == "ru"
    manifest = read_json(bundle / "manifest.json")
    assert manifest["language"] == "ru"
    assert manifest["language_origin"] == "user"


def test_transcript_json_keeps_segments_exactly_as_spoken(
    lecture_file: Path, tmp_path: Path, fake_transcriber: FakeTranscriber
) -> None:
    bundle = tmp_path / "bundle"

    main(["extract", str(lecture_file), "-o", str(bundle)], transcriber_factory=fake_transcriber)

    transcript = read_json(bundle / "transcript.json")
    assert transcript["language"] == "en"
    assert transcript["segments"] == [
        {"start": 0.0, "end": 1.8, "text": "First we assign one to a and print it."},
        {"start": 2.0, "end": 3.9, "text": "Then we check whether a equals one."},
        {"start": 4.0, "end": 5.9, "text": 'els Принт А из нот единица print("a is not 1")'},
    ]


def test_transcript_markdown_is_readable_paragraphs_with_timestamps(
    lecture_file: Path, tmp_path: Path
) -> None:
    bundle = tmp_path / "bundle"
    transcriber = FakeTranscriber(
        segments=[
            Segment(start=0.0, end=2.0, text="Hello."),
            Segment(start=2.1, end=4.0, text="Today: loops."),
            # a pause of more than a few seconds starts a new paragraph
            Segment(start=9.0, end=11.0, text="Next, a for loop."),
            Segment(start=3725.0, end=3727.0, text="Past the hour."),
        ]
    )

    main(["extract", str(lecture_file), "-o", str(bundle), "--no-frames"],
         transcriber_factory=transcriber)

    assert (bundle / "transcript.md").read_text(encoding="utf-8") == (
        "# lecture\n"
        "\n"
        "**[00:00]** Hello. Today: loops.\n"
        "\n"
        "**[00:09]** Next, a for loop.\n"
        "\n"
        "**[1:02:05]** Past the hour.\n"
    )


def _one_line_error(capsys: pytest.CaptureFixture[str]) -> str:
    err = capsys.readouterr().err
    assert "Traceback" not in err
    assert err.count("\n") == 1, f"expected exactly one line, got: {err!r}"
    return err


def test_missing_ffmpeg_is_a_one_line_error(
    lecture_file: Path, tmp_path: Path, fake_transcriber: FakeTranscriber,
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.setenv("PATH", str(tmp_path / "empty"))

    exit_code = main(["extract", str(lecture_file), "-o", str(tmp_path / "b")], transcriber_factory=fake_transcriber)

    assert exit_code == 1
    assert "ffmpeg" in _one_line_error(capsys)
    assert not (tmp_path / "b").exists()


def test_missing_file_is_a_one_line_error(
    tmp_path: Path, fake_transcriber: FakeTranscriber, capsys: pytest.CaptureFixture[str]
) -> None:
    missing = tmp_path / "nope.mp4"

    exit_code = main(["extract", str(missing), "-o", str(tmp_path / "b")], transcriber_factory=fake_transcriber)

    assert exit_code == 1
    err = _one_line_error(capsys)
    assert str(missing) in err and "no such file" in err


def test_unreadable_file_is_a_one_line_error(
    tmp_path: Path, fake_transcriber: FakeTranscriber, capsys: pytest.CaptureFixture[str]
) -> None:
    junk = tmp_path / "notes.mp4"
    junk.write_text("this is not a video", encoding="utf-8")

    exit_code = main(["extract", str(junk), "-o", str(tmp_path / "b")], transcriber_factory=fake_transcriber)

    assert exit_code == 1
    err = _one_line_error(capsys)
    assert str(junk) in err and "not a readable video or audio file" in err
    assert fake_transcriber.calls == []


def test_missing_whisper_extra_is_a_one_line_error(
    lecture_file: Path, tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.setitem(sys.modules, "faster_whisper", None)  # makes the import fail

    exit_code = main(["extract", str(lecture_file), "-o", str(tmp_path / "b")])

    assert exit_code == 1
    assert "lecture-notes[whisper]" in _one_line_error(capsys)


def test_transcript_markdown_shows_each_key_frame_where_it_appears(
    lecture_file: Path, tmp_path: Path, fake_transcriber: FakeTranscriber,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setitem(sys.modules, "pytesseract", None)  # OCR text has its own test
    bundle = tmp_path / "bundle"

    main(["extract", str(lecture_file), "-o", str(bundle)], transcriber_factory=fake_transcriber)

    # The fixture's slides change at 0, 2 and 4 s; each slide change starts a paragraph,
    # even though the speech has no pause there.
    assert (bundle / "transcript.md").read_text(encoding="utf-8") == (
        "# lecture\n"
        "\n"
        "![00:00](frames/frame_000000.jpg)\n"
        "\n"
        "**[00:00]** First we assign one to a and print it.\n"
        "\n"
        "![00:02](frames/frame_000002.jpg)\n"
        "\n"
        "**[00:02]** Then we check whether a equals one.\n"
        "\n"
        "![00:04](frames/frame_000004.jpg)\n"
        "\n"
        '**[00:04]** els Принт А из нот единица print("a is not 1")\n'
    )
