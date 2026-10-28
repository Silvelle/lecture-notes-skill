"""Seam 2: `lecture-notes verify` over hand-written (Lecture note, Lecture bundle) pairs."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from lecture_notes.cli import main

YOUTUBE = "https://www.youtube.com/watch?v=abc123"


def write_bundle(directory: Path, *, source: dict[str, str] | None = None) -> Path:
    """A 10-minute Lecture: speech at 0-20 s, 300-330 s and 590-600 s; Key frames at 0 s and 120 s."""
    directory.mkdir(parents=True, exist_ok=True)
    manifest = {
        "schema_version": 1,
        "source": source or {"kind": "local_file", "path": "/lectures/loops.mp4"},
        "duration": 600.0,
        "key_frames": {
            "status": "extracted",
            "min_interval": 30.0,
            "frames": [
                {"time": 0.0, "file": "frames/frame_000000.jpg"},
                {"time": 120.4, "file": "frames/frame_000120.jpg"},
            ],
        },
    }
    transcript = {
        "language": "en",
        "segments": [
            {"start": 0.0, "end": 10.0, "text": "Today: loops."},
            {"start": 10.0, "end": 20.0, "text": "A for loop repeats a block."},
            {"start": 300.0, "end": 330.0, "text": "A while loop checks a condition."},
            {"start": 590.0, "end": 600.0, "text": "That's all."},
        ],
    }
    (directory / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
    (directory / "transcript.json").write_text(json.dumps(transcript), encoding="utf-8")
    return directory


def run_verify(
    tmp_path: Path, note: str, capsys: pytest.CaptureFixture[str], **bundle: Any
) -> tuple[int, dict[str, Any]]:
    note_path = tmp_path / "note.md"
    note_path.write_text(note, encoding="utf-8")
    bundle_dir = write_bundle(tmp_path / "bundle", **bundle)
    exit_code = main(["verify", str(note_path), str(bundle_dir), "--json"])
    return exit_code, json.loads(capsys.readouterr().out)


VALID_NOTE = """\
# Loops

- A for loop repeats a block [00:12]
- A while loop checks a condition [05:05]
"""


def test_a_note_with_every_idea_cited_passes(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    exit_code, report = run_verify(tmp_path, VALID_NOTE, capsys)

    assert report == {"ok": True, "problems": []}
    assert exit_code == 0


RICH_NOTE = """\
---
title: Loops
source: https://www.youtube.com/watch?v=abc123
tags: [python, loops]
---

# Loops

## For loops

- A for loop repeats a block [00:12]
  - nested detail, still cited [00:15]
1. Numbered ideas count too [00:05]
> A quoted idea is an idea [05:10]

```python
for i in range(3):
    print(i)
```

```mermaid
graph TD
  for_loop --> while_loop
```

$$
\\sum_{i=0}^{n} i
$$

$$ x = 1 $$

> [!note] Loops
> A callout's body is an idea [00:12]
>

<!-- a comment -->
%% an Obsidian comment %%

Setext heading
==============

| Loop | Checks |
| ---- | ------ |
| for  | a range [00:12] |

---

- [unclear: the board is out of focus]
- Something was said here [unclear] [05:20]
"""


def test_structure_that_is_not_an_idea_needs_no_citation(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    exit_code, report = run_verify(tmp_path, RICH_NOTE, capsys)

    assert report == {"ok": True, "problems": []}
    assert exit_code == 0


# (note, [(line, problem code)]) — the Problems `verify` must report, in order.
PROBLEM_CASES: dict[str, tuple[str, list[tuple[int, str]]]] = {
    "missing Citation on a bullet": (
        "# Loops\n\n- A for loop repeats a block [00:12]\n- Loops are fast\n",
        [(4, "missing_citation")],
    ),
    "missing Citation on a paragraph line": (
        "Loops repeat code.\n",
        [(1, "missing_citation")],
    ),
    "a timestamp inside inline code is not a Citation": (
        "- Slicing works like `a[1:23]`\n",
        [(1, "missing_citation")],
    ),
    "timestamp past the end of the Lecture": (
        "- The last idea [10:01]\n",
        [(1, "timestamp_out_of_range")],
    ),
    "timestamp at the very end is in range": (
        "- That's all [10:00]\n",
        [],
    ),
    "timestamp with no segment or Key frame nearby": (
        "- Nothing was said or shown here [02:30]\n",
        [(1, "timestamp_not_near_content")],
    ),
    "timestamp next to a Key frame but no speech": (
        "- The slide shows a for loop [02:03]\n",
        [],
    ),
    "timestamp a few seconds before a segment": (
        "- A while loop checks a condition [04:56]\n",
        [],
    ),
    "each bad timestamp on a line is reported": (
        "- Two Citations [00:12] [02:30] [1:00:00]\n",
        [(1, "timestamp_not_near_content"), (1, "timestamp_out_of_range")],
    ),
    "an embedded Key frame is a Citation": (
        "![[frame_000120.jpg]]\n- The slide's loop ![[attachments/frame_000120.jpg|400]]\n"
        "- As drawn ![loop](frames/frame_000000.jpg)\n",
        [],
    ),
    "an embedded image that is not a Key frame": (
        "- A made-up frame ![[frame_000999.jpg]]\n- A diagram ![[diagram.png]] [00:12]\n"
        "- From the web ![x](https://example.com/x.png)\n",
        [(1, "unknown_frame"), (2, "unknown_frame"), (3, "unknown_frame")],
    ),
    "embedding another note is neither a Citation nor an image": (
        "- See ![[Loops overview]] [00:12]\n- Only a note embed ![[Loops overview]]\n",
        [(2, "missing_citation")],
    ),
    "a linked timestamp whose t= matches its label": (
        f"- A for loop [00:12]({YOUTUBE}&t=12)\n- A while loop [05:05](https://youtu.be/abc123?t=305s)\n"
        f"- Again [05:05]({YOUTUBE}&t=5m5s)\n",
        [],
    ),
    "a linked timestamp whose t= disagrees with its label": (
        f"- A for loop [00:12]({YOUTUBE}&t=305)\n",
        [(1, "link_time_mismatch")],
    ),
    "a #tag line is an idea, not a heading": (
        "#python loops are always faster than recursion\n",
        [(1, "missing_citation")],
    ),
    "a paragraph with a pipe before a rule is not a table header": (
        "a | b is union\n\n---\n",
        [(1, "missing_citation")],
    ),
    "an Unclear marker does not excuse a stated idea": (
        "- Python was invented in 1802 [unclear]\n- [unclear: inaudible]\n",
        [(1, "missing_citation")],
    ),
    "a wikilink that looks like a timestamp is not a Citation": (
        "- Loops [[00:12]]\n",
        [(1, "missing_citation")],
    ),
    "a fence line with an info string does not close a code block": (
        "```\nnot an idea\n```python\nstill code\n```\n",
        [],
    ),
    "images without an extension and HTML images are checked": (
        "- From the web ![x](https://img.example.com/abc) [00:12]\n"
        '- Drawn <img src="diagram.png"> [00:12]\n',
        [(1, "unknown_frame"), (2, "unknown_frame")],
    ),
    "an unclosed frontmatter block is not skipped": (
        "---\ntitle: Loops\n",
        [(2, "missing_citation")],
    ),
}


@pytest.mark.parametrize("note, expected", PROBLEM_CASES.values(), ids=PROBLEM_CASES.keys())
def test_problems_are_reported_by_line(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], note: str, expected: list[tuple[int, str]]
) -> None:
    exit_code, report = run_verify(tmp_path, note, capsys)

    assert [(p["line"], p["problem"]) for p in report["problems"]] == expected
    assert report["ok"] is (not expected)
    assert exit_code == (1 if expected else 0)
    assert all(p["message"] and p["suggestion"] for p in report["problems"])


def test_url_source_accepts_linked_and_plain_timestamps(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    note = f"- A for loop [00:12]({YOUTUBE}&t=12)\n- A while loop [05:05]\n"

    exit_code, report = run_verify(tmp_path, note, capsys, source={"kind": "url", "url": YOUTUBE})

    assert report == {"ok": True, "problems": []}
    assert exit_code == 0


def test_human_output_names_each_problem_by_file_and_line(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    note = tmp_path / "note.md"
    note.write_text("# Loops\n\n- Loops are fast\n- Ends here [10:01]\n", encoding="utf-8")

    exit_code = main(["verify", str(note), str(write_bundle(tmp_path / "bundle"))])

    out = capsys.readouterr().out
    assert exit_code == 1
    assert f"{note}:3: missing_citation:" in out
    assert f"{note}:4: timestamp_out_of_range:" in out
    assert out.rstrip().endswith("2 problems")


def test_human_output_for_a_passing_note(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    note = tmp_path / "note.md"
    note.write_text(VALID_NOTE, encoding="utf-8")

    exit_code = main(["verify", str(note), str(write_bundle(tmp_path / "bundle"))])

    assert exit_code == 0
    assert capsys.readouterr().out.startswith("OK")


@pytest.mark.parametrize("broken", ["no bundle", "no note", "bad manifest"])
def test_an_unreadable_note_or_bundle_exits_2_with_one_line(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], broken: str
) -> None:
    note = tmp_path / "note.md"
    bundle = write_bundle(tmp_path / "bundle")
    note.write_text(VALID_NOTE, encoding="utf-8")
    if broken == "no bundle":
        bundle = tmp_path / "missing"
    elif broken == "no note":
        note = tmp_path / "missing.md"
    else:
        (bundle / "manifest.json").write_text('{"schema_version": 1}', encoding="utf-8")

    exit_code = main(["verify", str(note), str(bundle), "--json"])

    captured = capsys.readouterr()
    assert exit_code == 2
    assert captured.out == ""
    assert captured.err.startswith("lecture-notes: error:") and captured.err.count("\n") == 1
