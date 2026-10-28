"""The yt-dlp downloader, driven through the CLI with yt_dlp.YoutubeDL stubbed out (no network)."""

from __future__ import annotations

import io
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


HUMAN_VTT = """WEBVTT
Kind: captions
Language: en

00:00:00.000 --> 00:00:02.500
Today: loops.

00:00:02.500 --> 00:00:05.000 align:start position:0%
A <i>for</i> loop
repeats a block.
"""

# YouTube's auto captions: word timings, each line repeated in the next cue, 10 ms cues.
AUTO_VTT = """WEBVTT
Kind: captions
Language: en

00:00:00.000 --> 00:00:01.990 align:start position:0%
today<00:00:00.500><c> loops</c>

00:00:01.990 --> 00:00:02.000 align:start position:0%
today loops

00:00:02.000 --> 00:00:04.000 align:start position:0%
today loops
els<00:00:02.400><c> print</c><00:00:02.800><c> a</c>
"""


class StubYoutubeDL:
    """Records the options each YoutubeDL is built with; serves the fixture Lecture."""

    instances: list[dict[str, Any]] = []
    video: Path
    error: str | None = None
    subtitles: dict[str, Any] = {}
    automatic_captions: dict[str, Any] = {}
    vtt: dict[str, str] = {}

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
        info = {**INFO, "subtitles": StubYoutubeDL.subtitles,
                "automatic_captions": StubYoutubeDL.automatic_captions}
        if not download:
            return info
        target = Path(self.params["outtmpl"].replace("%(ext)s", "mp4"))
        shutil.copy(StubYoutubeDL.video, target)
        return {**info, "requested_downloads": [{"filepath": str(target)}]}

    def urlopen(self, url: str) -> io.BytesIO:
        return io.BytesIO(StubYoutubeDL.vtt[url].encode("utf-8"))


@pytest.fixture
def stub_ytdlp(monkeypatch: pytest.MonkeyPatch, lecture_file: Path) -> type[StubYoutubeDL]:
    StubYoutubeDL.instances = []
    StubYoutubeDL.error = None
    StubYoutubeDL.video = lecture_file
    StubYoutubeDL.subtitles = {}
    StubYoutubeDL.automatic_captions = {}
    StubYoutubeDL.vtt = {}
    monkeypatch.setattr(yt_dlp, "YoutubeDL", StubYoutubeDL)
    return StubYoutubeDL


def test_url_is_downloaded_through_ytdlp_into_a_bundle(
    tmp_path: Path, fake_transcriber: FakeTranscriber, stub_ytdlp: type[StubYoutubeDL]
) -> None:
    bundle = tmp_path / "bundle"

    assert main(["extract", URL, "-o", str(bundle)], transcriber_factory=fake_transcriber) == 0

    manifest = read_json(bundle / "manifest.json")
    assert manifest["source"] == {"kind": "url", "url": URL}
    assert (manifest["title"], manifest["channel"]) == ("Python basics", "MEPhI")
    download = stub_ytdlp.instances[-1]
    assert "1080" in download["format"]
    assert download["noplaylist"] is True


def test_browser_cookies_are_never_read_without_the_flag(
    tmp_path: Path, fake_transcriber: FakeTranscriber, stub_ytdlp: type[StubYoutubeDL]
) -> None:
    main(["extract", URL, "-o", str(tmp_path / "b")], transcriber_factory=fake_transcriber)

    assert stub_ytdlp.instances
    assert all("cookiesfrombrowser" not in params for params in stub_ytdlp.instances)
    assert all("cookiefile" not in params for params in stub_ytdlp.instances)


def test_browser_cookies_are_used_when_asked(
    tmp_path: Path, fake_transcriber: FakeTranscriber, stub_ytdlp: type[StubYoutubeDL]
) -> None:
    main(["extract", URL, "-o", str(tmp_path / "b"), "--cookies-from-browser", "firefox:work"],
         transcriber_factory=fake_transcriber)

    assert all(p["cookiesfrombrowser"] == ("firefox", "work", None, None)
               for p in stub_ytdlp.instances)


def test_ytdlp_bot_check_becomes_the_blocked_message(
    tmp_path: Path, fake_transcriber: FakeTranscriber, stub_ytdlp: type[StubYoutubeDL],
    capsys: pytest.CaptureFixture[str],
) -> None:
    stub_ytdlp.error = "Sign in to confirm you're not a bot. Use --cookies-from-browser"

    exit_code = main(["extract", URL, "-o", str(tmp_path / "b")], transcriber_factory=fake_transcriber)

    err = capsys.readouterr().err
    assert exit_code == 1
    assert "Ways out" in err and "Traceback" not in err


def test_other_ytdlp_errors_are_one_line(
    tmp_path: Path, fake_transcriber: FakeTranscriber, stub_ytdlp: type[StubYoutubeDL],
    capsys: pytest.CaptureFixture[str],
) -> None:
    stub_ytdlp.error = "Video unavailable"

    exit_code = main(["extract", URL, "-o", str(tmp_path / "b")], transcriber_factory=fake_transcriber)

    err = capsys.readouterr().err
    assert exit_code == 1
    assert err.count("\n") == 1 and "Video unavailable" in err


def track(url: str) -> list[dict[str, str]]:
    return [{"ext": "json3", "url": url + ".json3"}, {"ext": "vtt", "url": url}]


def test_human_subtitles_are_parsed_from_vtt(
    tmp_path: Path, fake_transcriber: FakeTranscriber, stub_ytdlp: type[StubYoutubeDL]
) -> None:
    stub_ytdlp.subtitles = {"ru": track("https://subs/ru"), "live_chat": track("https://chat")}
    stub_ytdlp.vtt = {"https://subs/ru": HUMAN_VTT}
    bundle = tmp_path / "bundle"

    assert main(["extract", URL, "-o", str(bundle)], transcriber_factory=fake_transcriber) == 0

    assert read_json(bundle / "manifest.json")["transcript_origin"] == "human_subtitles"
    assert read_json(bundle / "transcript.json")["segments"] == [
        {"start": 0.0, "end": 2.5, "text": "Today: loops."},
        {"start": 2.5, "end": 5.0, "text": "A for loop repeats a block."},
    ]


def test_auto_subtitles_lose_youtubes_repeated_lines_and_word_timings(
    tmp_path: Path, fake_transcriber: FakeTranscriber, stub_ytdlp: type[StubYoutubeDL]
) -> None:
    stub_ytdlp.automatic_captions = {"ru-orig": track("https://auto/ru"), "en": track("https://x")}
    stub_ytdlp.vtt = {"https://auto/ru": AUTO_VTT}
    bundle = tmp_path / "bundle"

    main(["extract", URL, "-o", str(bundle), "--allow-auto-subs"], transcriber_factory=fake_transcriber)

    assert read_json(bundle / "manifest.json")["transcript_origin"] == "auto_subtitles"
    assert read_json(bundle / "transcript.json")["segments"] == [
        {"start": 0.0, "end": 1.99, "text": "today loops"},
        {"start": 2.0, "end": 4.0, "text": "els print a"},
    ]
