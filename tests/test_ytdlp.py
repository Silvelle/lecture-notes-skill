"""The yt-dlp downloader, driven through the CLI with yt_dlp.YoutubeDL stubbed out (no network)."""

from __future__ import annotations

import shutil
from pathlib import Path
from typing import Any

import pytest
import yt_dlp
from yt_dlp.utils import DownloadError

from lecture_notes.cli import main
from tests.conftest import FakeTranscriber, read_json

URL = "https://www.youtube.com/watch?v=abc123"
INFO = {
    "webpage_url": URL,
    "title": "Python basics",
    "channel": "MEPhI",
    "duration": 6,
    "language": "ru",
}


class StubYoutubeDL:
    """Records the options each YoutubeDL is built with; serves the fixture Lecture."""

    instances: list[dict[str, Any]] = []
    video: Path
    error: str | None = None

    def __init__(self, params: dict[str, Any]) -> None:
        self.params = params
        StubYoutubeDL.instances.append(params)

    def __enter__(self) -> StubYoutubeDL:
        return self

    def __exit__(self, *exc: object) -> None:
        return None

    def extract_info(self, url: str, download: bool = True) -> dict[str, Any]:
        if StubYoutubeDL.error:
            raise DownloadError(f"ERROR: [youtube] abc123: {StubYoutubeDL.error}")
        if not download:
            return dict(INFO)
        target = Path(self.params["outtmpl"].replace("%(ext)s", "mp4"))
        shutil.copy(StubYoutubeDL.video, target)
        return {**INFO, "requested_downloads": [{"filepath": str(target)}]}


@pytest.fixture
def stub_ytdlp(monkeypatch: pytest.MonkeyPatch, lecture_file: Path) -> type[StubYoutubeDL]:
    StubYoutubeDL.instances = []
    StubYoutubeDL.error = None
    StubYoutubeDL.video = lecture_file
    monkeypatch.setattr(yt_dlp, "YoutubeDL", StubYoutubeDL)
    return StubYoutubeDL


def test_url_is_downloaded_through_ytdlp_into_a_bundle(
    tmp_path: Path, fake_transcriber: FakeTranscriber, stub_ytdlp: type[StubYoutubeDL]
) -> None:
    bundle = tmp_path / "bundle"

    assert main(["extract", URL, "-o", str(bundle)], transcriber=fake_transcriber) == 0

    manifest = read_json(bundle / "manifest.json")
    assert manifest["source"] == {"kind": "url", "url": URL}
    assert (manifest["title"], manifest["channel"]) == ("Python basics", "MEPhI")
    download = stub_ytdlp.instances[-1]
    assert "1080" in download["format"]
    assert download["noplaylist"] is True


def test_browser_cookies_are_never_read_without_the_flag(
    tmp_path: Path, fake_transcriber: FakeTranscriber, stub_ytdlp: type[StubYoutubeDL]
) -> None:
    main(["extract", URL, "-o", str(tmp_path / "b")], transcriber=fake_transcriber)

    assert stub_ytdlp.instances
    assert all("cookiesfrombrowser" not in params for params in stub_ytdlp.instances)
    assert all("cookiefile" not in params for params in stub_ytdlp.instances)


def test_browser_cookies_are_used_when_asked(
    tmp_path: Path, fake_transcriber: FakeTranscriber, stub_ytdlp: type[StubYoutubeDL]
) -> None:
    main(["extract", URL, "-o", str(tmp_path / "b"), "--cookies-from-browser", "firefox:work"],
         transcriber=fake_transcriber)

    assert all(p["cookiesfrombrowser"] == ("firefox", "work", None, None)
               for p in stub_ytdlp.instances)


def test_ytdlp_bot_check_becomes_the_blocked_message(
    tmp_path: Path, fake_transcriber: FakeTranscriber, stub_ytdlp: type[StubYoutubeDL],
    capsys: pytest.CaptureFixture[str],
) -> None:
    stub_ytdlp.error = "Sign in to confirm you're not a bot. Use --cookies-from-browser"

    exit_code = main(["extract", URL, "-o", str(tmp_path / "b")], transcriber=fake_transcriber)

    err = capsys.readouterr().err
    assert exit_code == 1
    assert "Ways out" in err and "Traceback" not in err


def test_other_ytdlp_errors_are_one_line(
    tmp_path: Path, fake_transcriber: FakeTranscriber, stub_ytdlp: type[StubYoutubeDL],
    capsys: pytest.CaptureFixture[str],
) -> None:
    stub_ytdlp.error = "Video unavailable"

    exit_code = main(["extract", URL, "-o", str(tmp_path / "b")], transcriber=fake_transcriber)

    err = capsys.readouterr().err
    assert exit_code == 1
    assert err.count("\n") == 1 and "Video unavailable" in err
