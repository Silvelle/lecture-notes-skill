"""User settings: ~/.config/lecture-notes/config.toml (or under $XDG_CONFIG_HOME)."""

from __future__ import annotations

import json
import os
import tomllib
from pathlib import Path


def path() -> Path:
    base = os.environ.get("XDG_CONFIG_HOME") or str(Path.home() / ".config")
    return Path(base) / "lecture-notes" / "config.toml"


def get_vault() -> Path | None:
    """The remembered vault folder, or None if none was set."""
    try:
        settings = tomllib.loads(path().read_text(encoding="utf-8"))
    except (OSError, tomllib.TOMLDecodeError):
        return None
    vault = settings.get("vault")
    return Path(vault) if isinstance(vault, str) else None


def set_vault(vault: Path) -> Path:
    vault = vault.expanduser().resolve()
    config = path()
    config.parent.mkdir(parents=True, exist_ok=True)
    # A JSON string is a valid TOML basic string, quotes and backslashes escaped.
    config.write_text(f"vault = {json.dumps(str(vault))}\n", encoding="utf-8")
    return vault
