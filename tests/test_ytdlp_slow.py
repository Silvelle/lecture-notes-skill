"""Opt-in: a real yt-dlp download of a short public video (`pytest -m slow`)."""

from __future__ import annotations

from pathlib import Path

import pytest

from lecture_notes.cli import main
from tests.conftest import FakeTranscriber, read_json

pytestmark = pytest.mark.slow

ME_AT_THE_ZOO = "https://www.youtube.com/watch?v=jNQXAC9IVRw&t=3s"  # 19 s, first YouTube video


def test_real_youtube_video_becomes_a_bundle(
    tmp_path: Path, fake_transcriber: FakeTranscriber, capsys: pytest.CaptureFixture[str]
) -> None:
    bundle = tmp_path / "bundle"

    exit_code = main(["extract", ME_AT_THE_ZOO, "-o", str(bundle)], transcriber_factory=fake_transcriber)

    if exit_code != 0 and "blocked by the site" in capsys.readouterr().err:
        pytest.skip("YouTube blocked this machine (bot check); nothing else to test here")
    assert exit_code == 0
    manifest = read_json(bundle / "manifest.json")
    assert manifest["source"]["url"] == "https://www.youtube.com/watch?v=jNQXAC9IVRw"
    assert manifest["title"] == "Me at the zoo"
    assert 17 <= manifest["duration"] <= 21
    assert manifest["key_frames"]["frames"]
