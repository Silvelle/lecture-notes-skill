"""`lecture-notes doctor`: what this machine can do."""

from __future__ import annotations

import stat
from pathlib import Path

import pytest

from lecture_notes.cli import main


def fake_path(tmp_path: Path, *tools: str) -> str:
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    for tool in tools:
        exe = bin_dir / tool
        exe.write_text("#!/bin/sh\n", encoding="utf-8")
        exe.chmod(exe.stat().st_mode | stat.S_IEXEC)
    return str(bin_dir)


def test_doctor_reports_tools_and_a_missing_js_runtime(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setenv("PATH", fake_path(tmp_path, "ffmpeg", "ffprobe"))

    exit_code = main(["doctor"])

    out = capsys.readouterr().out
    assert exit_code == 0
    assert "ffmpeg" in out and "ok" in out
    assert "JS runtime" in out and "missing" in out and "deno" in out


def test_doctor_finds_deno(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setenv("PATH", fake_path(tmp_path, "ffmpeg", "ffprobe", "deno"))

    main(["doctor"])

    js_line = next(l for l in capsys.readouterr().out.splitlines() if "JS runtime" in l)
    assert "deno" in js_line and "missing" not in js_line


def test_doctor_fails_without_ffmpeg(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setenv("PATH", fake_path(tmp_path))

    assert main(["doctor"]) == 1
    assert "ffmpeg" in capsys.readouterr().out
