"""The `lecture-notes` command line."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from lecture_notes.errors import LectureNotesError
from lecture_notes.extract import extract
from lecture_notes.frames import DEFAULT_MIN_INTERVAL
from lecture_notes.transcriber import Transcriber


def main(argv: list[str] | None = None, *, transcriber: Transcriber | None = None) -> int:
    parser = argparse.ArgumentParser(prog="lecture-notes")
    commands = parser.add_subparsers(dest="command", required=True)

    extract_cmd = commands.add_parser("extract", help="turn a Source into a Lecture bundle")
    extract_cmd.add_argument("source", type=Path, help="a local video or audio file")
    extract_cmd.add_argument("-o", "--output", type=Path, help="bundle folder (default: ./<file name>)")
    extract_cmd.add_argument("--lang", help="spoken language code, e.g. ru; skips detection")
    extract_cmd.add_argument(
        "--min-frame-interval", type=_positive_seconds, default=DEFAULT_MIN_INTERVAL,
        metavar="SECONDS",
        help=f"take a Key frame at least this often (default: {DEFAULT_MIN_INTERVAL:g})",
    )
    extract_cmd.add_argument("--no-frames", action="store_true", help="skip Key frames")

    args = parser.parse_args(argv)
    try:
        bundle = extract(
            args.source,
            args.output or Path(args.source.stem),
            transcriber=transcriber,
            language=args.lang,
            with_key_frames=not args.no_frames,
            min_frame_interval=args.min_frame_interval,
        )
    except LectureNotesError as error:
        print(f"lecture-notes: error: {error}", file=sys.stderr)
        return 1
    print(bundle)
    return 0


def _positive_seconds(value: str) -> float:
    try:
        seconds = float(value)
    except ValueError:
        seconds = 0.0
    if seconds <= 0:
        raise argparse.ArgumentTypeError(f"must be a positive number of seconds, got {value!r}")
    return seconds


if __name__ == "__main__":
    sys.exit(main())
