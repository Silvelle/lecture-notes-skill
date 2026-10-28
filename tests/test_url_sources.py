"""Seam 1 + 3: `extract <URL>` through the downloader interface (no network)."""

from __future__ import annotations

from pathlib import Path

import pytest

from lecture_notes.cli import main
from lecture_notes.sources import SourceBlocked
from tests.conftest import FakeDownloader, FakeTranscriber, read_json

URL = "https://www.youtube.com/watch?v=abc123"


def test_url_source_becomes_a_bundle_with_lecture_metadata(
    tmp_path: Path, fake_transcriber: FakeTranscriber, fake_downloader: FakeDownloader
) -> None:
    bundle = tmp_path / "bundle"

    exit_code = main(["extract", URL, "-o", str(bundle)],
                     transcriber_factory=fake_transcriber, downloader=fake_downloader)

    assert exit_code == 0
    manifest = read_json(bundle / "manifest.json")
    assert manifest["source"] == {"kind": "url", "url": URL}
    assert manifest["title"] == "Python basics"
    assert manifest["channel"] == "MEPhI"
    assert manifest["duration"] == pytest.approx(6.0, abs=0.2)
    assert len(manifest["key_frames"]["frames"]) == 3
    assert read_json(bundle / "transcript.json")["segments"]


@pytest.mark.parametrize(
    "given, requested",
    [
        (f"{URL}&t=754s", URL),
        ("https://youtu.be/abc123?t=12", "https://youtu.be/abc123"),
        (f"{URL}&list=PL123&index=4", URL),
        ("https://www.youtube.com/watch?t=5&v=abc123", URL),
    ],
)
def test_start_time_and_playlist_parameters_are_dropped(
    tmp_path: Path, fake_transcriber: FakeTranscriber, fake_downloader: FakeDownloader,
    given: str, requested: str,
) -> None:
    main(["extract", given, "-o", str(tmp_path / "b")],
         transcriber_factory=fake_transcriber, downloader=fake_downloader)

    assert fake_downloader.requested == [requested]


def test_a_playlist_url_is_rejected_with_a_hint(
    tmp_path: Path, fake_transcriber: FakeTranscriber, fake_downloader: FakeDownloader,
    capsys: pytest.CaptureFixture[str],
) -> None:
    exit_code = main(["extract", "https://www.youtube.com/playlist?list=PL123", "-o", str(tmp_path / "b")],
                     transcriber_factory=fake_transcriber, downloader=fake_downloader)

    assert exit_code == 1
    assert "playlist" in capsys.readouterr().err
    assert fake_downloader.requested == []


def test_a_bot_block_explains_every_way_out(
    tmp_path: Path, fake_transcriber: FakeTranscriber, fake_downloader: FakeDownloader,
    capsys: pytest.CaptureFixture[str],
) -> None:
    fake_downloader.blocked = SourceBlocked("Sign in to confirm you're not a bot")

    exit_code = main(["extract", URL, "-o", str(tmp_path / "b")],
                     transcriber_factory=fake_transcriber, downloader=fake_downloader)

    err = capsys.readouterr().err
    assert exit_code == 1
    assert "Traceback" not in err
    assert "not a bot" in err
    assert "--cookies-from-browser" in err and "ban" in err
    assert "local file" in err
    assert "transcript-only" in err
    assert not (tmp_path / "b").exists()
