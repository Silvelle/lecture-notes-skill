"""`lecture-notes config`: the remembered vault folder."""

from __future__ import annotations

from pathlib import Path

import pytest

from lecture_notes.cli import main


@pytest.fixture(autouse=True)
def config_home(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    home = tmp_path / "config"
    monkeypatch.setenv("XDG_CONFIG_HOME", str(home))
    return home


def test_vault_is_unset_at_first(capsys: pytest.CaptureFixture[str]) -> None:
    assert main(["config", "vault"]) == 1
    assert "no vault set" in capsys.readouterr().err


def test_vault_is_remembered(
    tmp_path: Path, config_home: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    vault = tmp_path / "Obsidian Vault" / "Lectures"

    assert main(["config", "vault", str(vault)]) == 0
    capsys.readouterr()
    assert main(["config", "vault"]) == 0

    assert capsys.readouterr().out.strip() == str(vault.resolve())
    assert (config_home / "lecture-notes" / "config.toml").is_file()


def test_a_relative_vault_is_stored_as_an_absolute_path(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.chdir(tmp_path)

    main(["config", "vault", "notes"])
    capsys.readouterr()
    main(["config", "vault"])

    assert capsys.readouterr().out.strip() == str(tmp_path / "notes")
