"""The agent skill: SKILL.md fields, and the note format it teaches passes `verify`."""

from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

from lecture_notes.cli import main

SKILL_DIR = Path(__file__).parent.parent / "skills" / "lecture-notes"
# https://agentskills.io/specification
AGENTSKILLS_FIELDS = {"name", "description", "license", "compatibility", "metadata", "allowed-tools"}


def frontmatter(text: str) -> dict[str, str]:
    match = re.match(r"^---\n(.*?)\n---\n", text, re.DOTALL)
    assert match, "SKILL.md must start with YAML frontmatter"
    fields = {}
    for line in match.group(1).splitlines():
        key, _, value = line.partition(":")
        fields[key.strip()] = value.strip()
    return fields


def test_skill_frontmatter_uses_only_agentskills_fields() -> None:
    fields = frontmatter((SKILL_DIR / "SKILL.md").read_text(encoding="utf-8"))

    assert set(fields) <= AGENTSKILLS_FIELDS
    assert fields["name"] == SKILL_DIR.name
    assert re.fullmatch(r"[a-z0-9]+(-[a-z0-9]+)*", fields["name"]) and len(fields["name"]) <= 64
    assert 0 < len(fields["description"]) <= 1024
    assert len(fields.get("compatibility", "")) <= 500


def test_every_file_the_skill_links_exists() -> None:
    text = (SKILL_DIR / "SKILL.md").read_text(encoding="utf-8")
    for target in re.findall(r"\]\(([^)#:]+\.md)\)", text):
        assert (SKILL_DIR / target).is_file(), target


def test_the_example_note_in_the_format_passes_verify(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    text = (SKILL_DIR / "note-format.md").read_text(encoding="utf-8")
    example = re.search(r"````markdown\n(.*?)\n````", text, re.DOTALL)
    assert example
    note = tmp_path / "note.md"
    note.write_text(example.group(1), encoding="utf-8")
    bundle = tmp_path / "bundle"
    bundle.mkdir()
    (bundle / "manifest.json").write_text(json.dumps({
        "duration": 9730.0,
        "key_frames": {"frames": [{"time": 760.2, "file": "frames/frame_000760.jpg"}]},
    }), encoding="utf-8")
    (bundle / "transcript.json").write_text(json.dumps({"segments": [
        {"start": 754.0, "end": 770.0, "text": "..."},
        {"start": 3910.0, "end": 3920.0, "text": "..."},
    ]}), encoding="utf-8")

    exit_code = main(["verify", str(note), str(bundle), "--json"])

    assert json.loads(capsys.readouterr().out) == {"ok": True, "problems": []}
    assert exit_code == 0
