"""Optional OCR of Key frames (tesseract), observed through the bundle and `doctor`."""

from __future__ import annotations

import shutil
import stat
import sys
from pathlib import Path

import pytest

from lecture_notes.cli import main
from tests.conftest import FakeTranscriber, read_json

FAKE_TESSERACT = """#!/bin/sh
if [ "$1" = "--list-langs" ]; then
  printf 'List of available languages in "/usr/share/tessdata/" (%s):\\n' 2
  for lang in {langs}; do echo "$lang"; done
  exit 0
fi
if [ "$1" = "--version" ]; then echo "tesseract 5.5.0"; exit 0; fi
# pytesseract: tesseract <image> <output base> -l <langs> ...
echo "$4" > "$2.langs"
printf 'print("recognised")\\n' > "$2.txt"
"""


def install_fake_tesseract(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, langs: str) -> None:
    bin_dir = tmp_path / "fakebin"
    bin_dir.mkdir()
    exe = bin_dir / "tesseract"
    exe.write_text(FAKE_TESSERACT.replace("{langs}", langs), encoding="utf-8")
    exe.chmod(exe.stat().st_mode | stat.S_IEXEC)
    monkeypatch.setenv("PATH", f"{bin_dir}:{Path(shutil.which('ffmpeg') or '').parent}")


def test_key_frames_get_ocr_text_with_transcript_language_plus_english(
    lecture_file: Path, tmp_path: Path, fake_transcriber: FakeTranscriber,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    install_fake_tesseract(tmp_path, monkeypatch, "eng osd rus")
    bundle = tmp_path / "bundle"

    main(["extract", str(lecture_file), "-o", str(bundle), "--lang", "ru"],
         transcriber_factory=fake_transcriber)

    key_frames = read_json(bundle / "manifest.json")["key_frames"]
    assert key_frames["ocr_languages"] == ["rus", "eng"]
    for frame in key_frames["frames"]:
        text_file = bundle / frame["ocr_text"]
        assert text_file.read_text(encoding="utf-8").strip() == 'print("recognised")'


def test_a_missing_language_pack_falls_back_to_english_with_a_warning(
    lecture_file: Path, tmp_path: Path, fake_transcriber: FakeTranscriber,
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str],
) -> None:
    install_fake_tesseract(tmp_path, monkeypatch, "eng osd")
    bundle = tmp_path / "bundle"

    main(["extract", str(lecture_file), "-o", str(bundle), "--lang", "ru"],
         transcriber_factory=fake_transcriber)

    assert read_json(bundle / "manifest.json")["key_frames"]["ocr_languages"] == ["eng"]
    assert "tesseract-ocr-rus" in capsys.readouterr().err


def test_without_the_ocr_extra_the_bundle_has_no_ocr(
    lecture_file: Path, tmp_path: Path, fake_transcriber: FakeTranscriber,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    install_fake_tesseract(tmp_path, monkeypatch, "eng")
    monkeypatch.setitem(sys.modules, "pytesseract", None)
    bundle = tmp_path / "bundle"

    assert main(["extract", str(lecture_file), "-o", str(bundle)],
                transcriber_factory=fake_transcriber) == 0

    key_frames = read_json(bundle / "manifest.json")["key_frames"]
    assert key_frames["ocr_languages"] is None
    assert all(f["ocr_text"] is None for f in key_frames["frames"])
    assert not list((bundle / "frames").glob("*.txt"))


def test_doctor_reports_tesseract_and_its_language_packs(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    install_fake_tesseract(tmp_path, monkeypatch, "eng osd")

    main(["doctor"])

    line = next(l for l in capsys.readouterr().out.splitlines() if l.startswith("tesseract"))
    assert "ok" in line and "eng" in line and "tesseract-ocr-rus" in line


@pytest.mark.skipif(shutil.which("tesseract") is None, reason="needs tesseract installed")
def test_real_tesseract_reads_the_code_on_the_fixture_slides(
    lecture_file: Path, tmp_path: Path, fake_transcriber: FakeTranscriber
) -> None:
    bundle = tmp_path / "bundle"

    main(["extract", str(lecture_file), "-o", str(bundle), "--lang", "en"],
         transcriber_factory=fake_transcriber)

    frames = read_json(bundle / "manifest.json")["key_frames"]["frames"]
    # tesseract may drop the spaces around operators; compare without whitespace
    texts = ["".join((bundle / f["ocr_text"]).read_text(encoding="utf-8").split()) for f in frames]
    assert "print(a)" in texts[0]
    assert "ifa==1:" in texts[1]
    assert 'print("aisnot1")' in texts[2]
