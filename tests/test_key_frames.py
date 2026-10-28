"""Seam 1: Key frames written by `extract`, observed through the Lecture bundle."""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from lecture_notes.cli import main
from tests.conftest import FakeTranscriber, read_json
from tests.fixture_lecture import DEFAULT_SLIDES, make_lecture

SLIDE_SECONDS = 2.0  # the fixture's seconds per slide


def test_one_key_frame_per_slide_timed_within_the_slide(
    lecture_file: Path, tmp_path: Path, fake_transcriber: FakeTranscriber
) -> None:
    bundle = tmp_path / "bundle"

    main(["extract", str(lecture_file), "-o", str(bundle)], transcriber_factory=fake_transcriber)

    key_frames = read_json(bundle / "manifest.json")["key_frames"]
    assert key_frames["status"] == "extracted"
    frames = key_frames["frames"]
    assert len(frames) == 3
    for slide, frame in enumerate(frames):
        assert slide * SLIDE_SECONDS <= frame["time"] < (slide + 1) * SLIDE_SECONDS
        assert (bundle / frame["file"]).is_file()
        assert frame["file"] == f"frames/frame_{int(frame['time']):06d}.jpg"


def test_a_slide_shown_again_is_not_a_new_key_frame(
    tmp_path: Path, fake_transcriber: FakeTranscriber
) -> None:
    first, second = DEFAULT_SLIDES[0], DEFAULT_SLIDES[1]
    lecture = make_lecture(tmp_path / "fixture", slides=[first, second, first], speech=False)
    bundle = tmp_path / "bundle"

    main(["extract", str(lecture), "-o", str(bundle)], transcriber_factory=fake_transcriber)

    frames = read_json(bundle / "manifest.json")["key_frames"]["frames"]
    assert [int(f["time"] // SLIDE_SECONDS) for f in frames] == [0, 1]
    assert sorted(p.name for p in (bundle / "frames").glob("*.jpg")) == [
        Path(f["file"]).name for f in frames
    ]


def test_min_frame_interval_adds_frames_on_a_long_static_slide(
    tmp_path: Path, fake_transcriber: FakeTranscriber
) -> None:
    lecture = make_lecture(
        tmp_path / "fixture", slides=[DEFAULT_SLIDES[0]], seconds_per_slide=10.0, speech=False
    )
    bundle = tmp_path / "bundle"

    main(["extract", str(lecture), "-o", str(bundle), "--min-frame-interval", "3"],
         transcriber_factory=fake_transcriber)

    key_frames = read_json(bundle / "manifest.json")["key_frames"]
    assert key_frames["min_interval"] == 3.0
    assert [round(f["time"]) for f in key_frames["frames"]] == [0, 3, 6, 9]
    assert all((bundle / f["file"]).is_file() for f in key_frames["frames"])


def test_no_frames_option_skips_key_frames_and_the_manifest_says_so(
    lecture_file: Path, tmp_path: Path, fake_transcriber: FakeTranscriber
) -> None:
    bundle = tmp_path / "bundle"

    main(["extract", str(lecture_file), "-o", str(bundle), "--no-frames"], transcriber_factory=fake_transcriber)

    assert read_json(bundle / "manifest.json")["key_frames"] == {
        "status": "skipped", "min_interval": None, "frames": [], "ocr_languages": None,
    }
    assert not (bundle / "frames").exists()
    assert (bundle / "transcript.json").is_file()


def test_audio_only_source_gets_a_bundle_without_key_frames(
    tmp_path: Path, fake_transcriber: FakeTranscriber
) -> None:
    audio = tmp_path / "talk.m4a"
    subprocess.run(
        ["ffmpeg", "-loglevel", "error", "-f", "lavfi", "-i", "sine=frequency=440:duration=3",
         "-c:a", "aac", str(audio)],
        check=True,
    )
    bundle = tmp_path / "bundle"

    assert main(["extract", str(audio), "-o", str(bundle)], transcriber_factory=fake_transcriber) == 0

    assert read_json(bundle / "manifest.json")["key_frames"] == {
        "status": "no_video", "min_interval": None, "frames": [], "ocr_languages": None,
    }


def test_a_slide_dropped_for_sharing_a_second_is_kept_when_it_returns(
    tmp_path: Path, fake_transcriber: FakeTranscriber
) -> None:
    a, b, c = DEFAULT_SLIDES
    # 0.6 s slides: A 0.0, B 0.6 (same second as A), C 1.2, C, C, B again at 3.0
    lecture = make_lecture(
        tmp_path / "fixture", slides=[a, b, c, c, c, b], seconds_per_slide=0.6, speech=False
    )
    bundle = tmp_path / "bundle"

    main(["extract", str(lecture), "-o", str(bundle)], transcriber_factory=fake_transcriber)

    frames = read_json(bundle / "manifest.json")["key_frames"]["frames"]
    assert [int(f["time"]) for f in frames] == [0, 1, 3]


def test_min_frame_interval_must_be_positive(
    lecture_file: Path, tmp_path: Path, fake_transcriber: FakeTranscriber
) -> None:
    with pytest.raises(SystemExit) as exit_info:
        main(["extract", str(lecture_file), "-o", str(tmp_path / "b"), "--min-frame-interval", "0"],
             transcriber_factory=fake_transcriber)
    assert exit_info.value.code == 2


def test_re_extracting_leaves_no_stale_key_frames(
    lecture_file: Path, tmp_path: Path, fake_transcriber: FakeTranscriber
) -> None:
    bundle = tmp_path / "bundle"
    main(["extract", str(lecture_file), "-o", str(bundle), "--min-frame-interval", "1"],
         transcriber_factory=fake_transcriber)

    main(["extract", str(lecture_file), "-o", str(bundle)], transcriber_factory=fake_transcriber)

    listed = {Path(f["file"]).name for f in read_json(bundle / "manifest.json")["key_frames"]["frames"]}
    assert {p.name for p in (bundle / "frames").glob("*.jpg")} == listed
    assert {p.stem for p in (bundle / "frames").glob("*.txt")} <= {Path(n).stem for n in listed}
