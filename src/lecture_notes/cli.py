"""The `lecture-notes` command line."""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import asdict
from pathlib import Path

from lecture_notes import config, doctor, errors
from lecture_notes.errors import LectureNotesError
from lecture_notes.extract import TranscriberFactory, extract, plan
from lecture_notes.frames import DEFAULT_MIN_INTERVAL
from lecture_notes.sources import Downloader
from lecture_notes import hardware as hardware_module
from lecture_notes.hardware import DeviceReport
from lecture_notes.verify import verify


def main(
    argv: list[str] | None = None,
    *,
    transcriber_factory: TranscriberFactory | None = None,
    downloader: Downloader | None = None,
    hardware: DeviceReport | None = None,
) -> int:
    parser = argparse.ArgumentParser(prog="lecture-notes")
    commands = parser.add_subparsers(dest="command", required=True)

    extract_cmd = commands.add_parser("extract", help="turn a Source into a Lecture bundle")
    extract_cmd.add_argument(
        "source", help="a URL (YouTube or any site yt-dlp supports) or a local video/audio file"
    )
    extract_cmd.add_argument("-o", "--output", type=Path, help="bundle folder (default: ./<title>)")
    extract_cmd.add_argument("--lang", help="spoken language code, e.g. ru; skips detection")
    extract_cmd.add_argument(
        "--min-frame-interval", type=_positive_seconds, default=DEFAULT_MIN_INTERVAL,
        metavar="SECONDS",
        help=f"take a Key frame at least this often (default: {DEFAULT_MIN_INTERVAL:g})",
    )
    extract_cmd.add_argument("--no-frames", action="store_true", help="skip Key frames")
    extract_cmd.add_argument("--model", help="speech model, e.g. small, medium, large-v3 "
                             "(default: chosen for this machine, see `doctor`)")
    extract_cmd.add_argument("--device", choices=["cpu", "cuda"], help="where to run it")
    extract_cmd.add_argument(
        "--backend", choices=list(hardware_module.BACKENDS),
        help="speech recognition backend (default: onnx-asr/GigaAM for Russian when installed)",
    )
    extract_cmd.add_argument("--yes", action="store_true",
                             help="don't ask before a long transcription on CPU")
    extract_cmd.add_argument(
        "--allow-auto-subs", action="store_true",
        help="use the site's auto-generated subtitles instead of local speech recognition "
        "(faster, but they garble code and terms)",
    )
    extract_cmd.add_argument(
        "--cookies-from-browser", metavar="BROWSER[:PROFILE]",
        help="use your browser's cookies for sites that block anonymous downloads; "
        "risks your account being flagged, so prefer a secondary account",
    )

    verify_cmd = commands.add_parser(
        "verify", help="check a Lecture note's Citations against its Lecture bundle"
    )
    verify_cmd.add_argument("note", type=Path, help="the Lecture note (Markdown)")
    verify_cmd.add_argument("bundle", type=Path, help="the Lecture bundle folder")
    verify_cmd.add_argument("--json", action="store_true", help="machine-readable output")
    verify_cmd.add_argument("--full", action="store_true",
                            help="the note is the full text: also flag speech it leaves out")

    extract_cmd.add_argument("--plan", action="store_true",
                             help="print what extract would do as JSON; download nothing")

    commands.add_parser("doctor", help="show what this machine can do")

    config_cmd = commands.add_parser("config", help="show or set remembered settings")
    config_cmd.add_argument("setting", choices=["vault"], help="vault: where notes go")
    config_cmd.add_argument("value", nargs="?", type=Path, help="new value; omit to show it")

    args = parser.parse_args(argv)
    if args.command == "doctor":
        lines, ready = doctor.report(hardware)
        print("\n".join(lines))
        return 0 if ready else 1
    if args.command == "config":
        return _config(args.value)
    if args.command == "verify":
        return _verify(args.note, args.bundle, as_json=args.json, full=args.full)
    if args.plan:
        try:
            result = plan(
                args.source, args.output, transcriber_factory=transcriber_factory,
                downloader=downloader, hardware_report=hardware, model=args.model,
                device=args.device, backend=args.backend, assume_yes=args.yes,
                cookies_from_browser=args.cookies_from_browser, language=args.lang,
                allow_auto_subs=args.allow_auto_subs, with_key_frames=not args.no_frames,
            )
        except LectureNotesError as error:
            errors.report(str(error))
            return 1
        print(json.dumps(asdict(result), ensure_ascii=False, indent=2))
        return 0
    try:
        bundle = extract(
            args.source,
            args.output,
            transcriber_factory=transcriber_factory,
            downloader=downloader,
            hardware_report=hardware,
            model=args.model,
            device=args.device,
            backend=args.backend,
            assume_yes=args.yes,
            cookies_from_browser=args.cookies_from_browser,
            language=args.lang,
            allow_auto_subs=args.allow_auto_subs,
            with_key_frames=not args.no_frames,
            min_frame_interval=args.min_frame_interval,
        )
    except LectureNotesError as error:
        errors.report(str(error))
        return 1
    print(bundle)
    return 0


def _config(value: Path | None) -> int:
    if value is not None:
        print(config.set_vault(value))
        return 0
    vault = config.get_vault()
    if vault is None:
        errors.report("no vault set; set one with: lecture-notes config vault <folder>")
        return 1
    print(vault)
    return 0


def _verify(note: Path, bundle: Path, *, as_json: bool, full: bool) -> int:
    """Exit 0: every idea cited. 1: problems in the note. 2: note or bundle unreadable."""
    try:
        text = note.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        errors.report(f"cannot read {note}")
        return 2
    try:
        problems = verify(text, bundle, full=full)
    except LectureNotesError as error:
        errors.report(str(error))
        return 2
    if as_json:
        report = {"ok": not problems, "problems": [asdict(p) for p in problems]}
        print(json.dumps(report, ensure_ascii=False, indent=2))
    elif problems:
        for p in problems:
            where = f"{note}:{p.line}" if p.line else str(note)
            print(f"{where}: {p.problem}: {p.message}")
            print(f"    suggestion: {p.suggestion}")
        print(f"{len(problems)} problem{'s' if len(problems) != 1 else ''}")
    else:
        print("OK: every idea has a Citation that matches the Lecture bundle")
    return 1 if problems else 0


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
