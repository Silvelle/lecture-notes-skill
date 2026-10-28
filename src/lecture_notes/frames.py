"""Key frames: stills taken where the shown content changes."""

from __future__ import annotations

import re
import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

import imagehash
from PIL import Image

from lecture_notes.errors import LectureNotesError
from lecture_notes.media import tool

# Slides that differ only in a few lines of code score ~0.01-0.02 on ffmpeg's scene
# metric, while compression noise on a static slide scores ~0.0001.
SCENE_THRESHOLD = 0.005
MAX_WIDTH = 1920
HASH_WIDTH = 320  # candidates are hashed at this width; kept frames are re-read in full
# Perceptual-hash distance (of 256 bits) at or below which two frames show the same
# content. Distinct code slides measure 60+ apart, re-encodes of one slide 0; kept low
# so a slide that gains one bullet or one typed line still counts as new.
DUPLICATE_DISTANCE = 12
DEFAULT_MIN_INTERVAL = 30.0  # seconds

_PTS_TIME = re.compile(r"pts_time:\s*([0-9.]+)")


@dataclass(frozen=True)
class KeyFrame:
    time: float
    file: str  # relative to the bundle folder


@dataclass(frozen=True)
class KeyFrames:
    # "skipped": --no-frames; "no_video": audio-only Source; "video_blocked": transcript-only
    status: Literal["extracted", "skipped", "no_video", "video_blocked"]
    min_interval: float | None
    frames: list[KeyFrame]


SKIPPED = KeyFrames(status="skipped", min_interval=None, frames=[])
NO_VIDEO = KeyFrames(status="no_video", min_interval=None, frames=[])
VIDEO_BLOCKED = KeyFrames(status="video_blocked", min_interval=None, frames=[])


def extract_key_frames(
    source: Path, bundle_dir: Path, *, duration: float, min_interval: float
) -> KeyFrames:
    """Scene changes with near-duplicates removed, plus a frame at least every
    `min_interval` seconds so slow changes (code being typed) are not missed."""
    frames_dir = bundle_dir / "frames"
    frames_dir.mkdir(parents=True, exist_ok=True)
    kept: dict[str, KeyFrame] = {}

    def save_full_frame(time: float, tmp: Path) -> None:
        name = _file_name(time)
        with Image.open(_frame_at(source, time, tmp)) as image:
            image.convert("RGB").save(frames_dir / name, quality=90)
        kept[name] = KeyFrame(time=round(time, 3), file=f"frames/{name}")

    seen: list[imagehash.ImageHash] = []
    with tempfile.TemporaryDirectory() as tmp:
        for time, candidate in _scene_changes(source, Path(tmp)):
            with Image.open(candidate) as image:
                fingerprint = imagehash.phash(image, hash_size=16)
            candidate.unlink()
            # Citations resolve to the second, so the first frame of a second wins;
            # a frame dropped that way is not "seen" and can still be kept later.
            if _file_name(time) in kept:
                continue
            if any(fingerprint - other <= DUPLICATE_DISTANCE for other in seen):
                continue
            seen.append(fingerprint)
            save_full_frame(time, Path(tmp))
        times = sorted(f.time for f in kept.values())
        for time in _gaps(times, duration, min_interval):
            if _file_name(time) not in kept:
                save_full_frame(time, Path(tmp))
    frames = sorted(kept.values(), key=lambda f: f.time)
    return KeyFrames(status="extracted", min_interval=min_interval, frames=frames)


def remove_key_frames(bundle_dir: Path) -> None:
    """Delete Key frames left by an earlier run, so the folder matches the Manifest."""
    frames_dir = bundle_dir / "frames"
    if not frames_dir.is_dir():
        return
    for old in frames_dir.glob("frame_*.jpg"):
        old.unlink()
    if not any(frames_dir.iterdir()):
        frames_dir.rmdir()


def _file_name(time: float) -> str:
    return f"frame_{int(time):06d}.jpg"


def _gaps(times: list[float], duration: float, min_interval: float) -> list[float]:
    """Times that fill every stretch longer than `min_interval` without a frame."""
    filler: list[float] = []
    for start, end in zip([0.0, *times], [*times, duration]):
        t = start + min_interval
        while t < end - 0.5:  # not right before the next frame or the end
            filler.append(t)
            t += min_interval
    return filler


def _frame_at(source: Path, time: float, tmp: Path) -> Path:
    out = tmp / f"at_{time:.3f}.png"
    result = subprocess.run(
        [tool("ffmpeg"), "-y", "-loglevel", "error", "-ss", f"{time:.3f}", "-i", str(source),
         "-frames:v", "1", "-vf", f"scale='min({MAX_WIDTH},iw)':-2", str(out)],
        capture_output=True, text=True,
    )
    if result.returncode != 0 or not out.is_file():
        raise LectureNotesError(f"{source}: could not read the video frame at {time:.1f} s")
    return out


def _scene_changes(source: Path, tmp: Path) -> list[tuple[float, Path]]:
    """The first frame plus every frame whose scene score passes the threshold, as small
    candidate images for hashing (a long lecture can have thousands of them)."""
    result = subprocess.run(
        [tool("ffmpeg"), "-hide_banner", "-nostats", "-i", str(source), "-an",
         "-vf", f"select='eq(n,0)+gt(scene,{SCENE_THRESHOLD})',showinfo,"
                f"scale={HASH_WIDTH}:-2",
         "-fps_mode", "vfr", str(tmp / "candidate_%06d.png")],
        capture_output=True, text=True,
    )
    if result.returncode != 0:
        raise LectureNotesError(f"{source}: could not read video frames")
    times = [
        float(match.group(1))
        for line in result.stderr.splitlines()
        if "Parsed_showinfo" in line and (match := _PTS_TIME.search(line))
    ]
    images = sorted(tmp.glob("candidate_*.png"))
    return list(zip(times, images, strict=True))
