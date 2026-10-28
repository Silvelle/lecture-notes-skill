"""The `lecture-notes` command line."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from lecture_notes.errors import LectureNotesError
from lecture_notes.extract import extract
from lecture_notes.transcriber import Transcriber


def main(argv: list[str] | None = None, *, transcriber: Transcriber | None = None) -> int:
    parser = argparse.ArgumentParser(prog="lecture-notes")
    commands = parser.add_subparsers(dest="command", required=True)

    extract_cmd = commands.add_parser("extract", help="turn a Source into a Lecture bundle")
    extract_cmd.add_argument("source", type=Path, help="a local video or audio file")
    extract_cmd.add_argument("-o", "--output", type=Path, help="bundle folder (default: ./<file name>)")
    extract_cmd.add_argument("--lang", help="spoken language code, e.g. ru; skips detection")

    args = parser.parse_args(argv)
    try:
        bundle = extract(
            args.source,
            args.output or Path(args.source.stem),
            transcriber=transcriber,
            language=args.lang,
        )
    except LectureNotesError as error:
        print(f"lecture-notes: error: {error}", file=sys.stderr)
        return 1
    print(bundle)
    return 0


if __name__ == "__main__":
    sys.exit(main())
