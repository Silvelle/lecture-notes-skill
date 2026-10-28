"""Opt-in: real onnx-asr (GigaAM v3) on a synthesised Russian sample (`pytest -m slow`)."""

from __future__ import annotations

import importlib.util
import shutil
import subprocess
from pathlib import Path

import pytest

from lecture_notes import hardware
from lecture_notes.cli import main
from tests.conftest import read_json

pytestmark = [
    pytest.mark.slow,
    pytest.mark.skipif(shutil.which("espeak-ng") is None, reason="needs espeak-ng"),
    pytest.mark.skipif(importlib.util.find_spec("onnx_asr") is None, reason="needs the ru extra"),
]


def test_gigaam_transcribes_russian_speech(tmp_path: Path) -> None:
    sample = tmp_path / "lecture.wav"
    subprocess.run(["espeak-ng", "-v", "ru", "-s", "140", "-w", str(sample),
                    "Сегодня мы изучаем циклы. Цикл повторяет блок кода."], check=True)
    bundle = tmp_path / "bundle"
    report = hardware.DeviceReport(gpus=(), cpu_count=4,
                                   backends=frozenset({hardware.ONNX_ASR}))

    assert main(["extract", str(sample), "-o", str(bundle), "--lang", "ru", "--yes"],
                hardware=report) == 0

    manifest = read_json(bundle / "manifest.json")
    segments = read_json(bundle / "transcript.json")["segments"]
    assert (manifest["backend"], manifest["model"]) == ("onnx-asr", "gigaam-v3-e2e-rnnt")
    assert segments and all(0 <= s["start"] < s["end"] <= manifest["duration"] + 0.5 for s in segments)
    text = " ".join(s["text"] for s in segments).lower()
    assert "сегодня" in text and "цикл" in text and "блок" in text, (manifest["duration"], segments)
