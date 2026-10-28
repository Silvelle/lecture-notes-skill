# lecture-notes

Turn recorded lectures into faithful, timestamped text that a human or an agent can read and check.

> Early development. See the [spec](https://github.com/Silvelle/lecture-notes-skill/issues/1).

## Install

Requires Python ≥ 3.11 and [ffmpeg](https://ffmpeg.org) on `PATH`.

```bash
pip install 'lecture-notes[whisper]'
```

## Use

```bash
lecture-notes extract lecture.mp4 -o lecture-bundle
```

This writes a **Lecture bundle**:

- `manifest.json`: Source, duration, language, Transcript origin, model, device, tool version
- `transcript.json`: timestamped segments (`start`, `end`, `text`) in the spoken language
- `transcript.md`: the Transcript as readable paragraphs with timestamps

The language is detected automatically; pass `--lang ru` (or any code) to override it.

## Develop

```bash
python -m venv .venv && .venv/bin/pip install -e '.[whisper]' --group dev
.venv/bin/mypy && .venv/bin/pytest          # fast tests (fake transcriber)
.venv/bin/pytest -m slow                    # real faster-whisper; needs espeak-ng
```
