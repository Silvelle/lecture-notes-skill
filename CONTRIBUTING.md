# Contributing

Thanks for helping. Issues and ideas go in [GitHub Issues](https://github.com/Silvelle/lecture-notes-skill/issues).

## Set up

```bash
python -m venv .venv
.venv/bin/pip install -e '.[whisper,ocr]' --group dev
```

You need ffmpeg. For OCR tests, install `tesseract-ocr`.

## Check your change

```bash
.venv/bin/mypy
.venv/bin/pytest            # fast tests, no network or models
.venv/bin/pytest -m slow    # real models and downloads; needs espeak-ng
```

CI runs both on Python 3.11 and 3.14.

## How the code is tested

Tests run the real CLI and check what a user sees: the bundle, `verify`'s verdict, the error text. Fakes stand in for the downloader and the speech model, so fast tests need no network or GPU. Write a failing test first, then the code.

Words like Lecture bundle, Key frame and Citation have fixed meanings. See [CONTEXT.md](CONTEXT.md).

## The bundle is a contract

The skill reads what `extract` writes. A change to `manifest.json` or `transcript.json` can break existing notes. Say so in your pull request.

## Releasing

1. Bump `version` in `pyproject.toml` and `.claude-plugin/plugin.json`.
2. Push a tag: `git tag v0.2.0 && git push --tags`.
3. The Release workflow publishes to PyPI.

Once, before the first release, add a trusted publisher on PyPI for this repo, workflow `release.yml`, environment `pypi`.
