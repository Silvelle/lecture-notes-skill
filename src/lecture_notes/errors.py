import sys


class LectureNotesError(Exception):
    """An expected failure, reported to the user as one line instead of a traceback."""


def warn(message: str) -> None:
    """A one-line warning on stderr; the run continues."""
    print(f"lecture-notes: warning: {message}", file=sys.stderr)


def report(error: str) -> None:
    """A one-line error on stderr, for the CLI to print before exiting."""
    print(f"lecture-notes: error: {error}", file=sys.stderr)
