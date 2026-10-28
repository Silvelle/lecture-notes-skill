"""Speech-recognition backends: onnx-asr (GigaAM) preferred for Russian when installed."""

from __future__ import annotations

from pathlib import Path

import pytest

from lecture_notes.cli import main
from lecture_notes.hardware import DeviceReport
from tests.conftest import FakeTranscriber, read_json

WITH_ONNX = DeviceReport(gpus=(), cpu_count=8, backends=frozenset({"faster-whisper", "onnx-asr"}))
WHISPER_ONLY = DeviceReport(gpus=(), cpu_count=8, backends=frozenset({"faster-whisper"}))


def extract(tmp_path: Path, lecture: Path, fake: FakeTranscriber, report: DeviceReport,
            *args: str) -> dict[str, object]:
    bundle = tmp_path / "bundle"
    assert main(["extract", str(lecture), "-o", str(bundle), *args],
                transcriber_factory=fake, hardware=report) == 0
    manifest: dict[str, object] = read_json(bundle / "manifest.json")
    return manifest


def test_russian_lecture_prefers_gigaam_when_onnx_asr_is_installed(
    lecture_file: Path, tmp_path: Path, fake_transcriber: FakeTranscriber
) -> None:
    manifest = extract(tmp_path, lecture_file, fake_transcriber, WITH_ONNX, "--lang", "ru")

    assert fake_transcriber.choice is not None
    assert fake_transcriber.choice.backend == "onnx-asr"
    assert (manifest["backend"], manifest["model"]) == ("onnx-asr", "gigaam-v3-e2e-rnnt")


@pytest.mark.parametrize(
    "report, args",
    [(WHISPER_ONLY, ["--lang", "ru"]), (WITH_ONNX, ["--lang", "en"]), (WITH_ONNX, [])],
    ids=["onnx-asr not installed", "not Russian", "language unknown"],
)
def test_otherwise_faster_whisper_is_used(
    lecture_file: Path, tmp_path: Path, fake_transcriber: FakeTranscriber,
    report: DeviceReport, args: list[str],
) -> None:
    manifest = extract(tmp_path, lecture_file, fake_transcriber, report, *args)

    assert manifest["backend"] == "faster-whisper"
    assert manifest["model"] == "small"


def test_backend_option_overrides_and_is_recorded(
    lecture_file: Path, tmp_path: Path, fake_transcriber: FakeTranscriber
) -> None:
    manifest = extract(tmp_path, lecture_file, fake_transcriber, WITH_ONNX,
                       "--lang", "ru", "--backend", "faster-whisper")

    assert (manifest["backend"], manifest["model"]) == ("faster-whisper", "small")


def test_choosing_a_backend_that_is_not_installed_says_how_to_install_it(
    lecture_file: Path, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    code = main(["extract", str(lecture_file), "-o", str(tmp_path / "b"), "--backend", "onnx-asr"],
                hardware=WHISPER_ONLY)

    assert code == 1
    assert "lecture-notes[ru]" in capsys.readouterr().err
