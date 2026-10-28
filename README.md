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

- `manifest.json`: Source, duration, language, Transcript origin, model, device, tool version, and the Key frame list
- `transcript.json`: timestamped segments (`start`, `end`, `text`) in the spoken language
- `transcript.md`: the Transcript as readable paragraphs with timestamps
- `frames/frame_<seconds>.jpg`: Key frames wherever the shown content changes (near-duplicates removed), plus at least one every 30 s

The language is detected automatically; pass `--lang ru` (or any code) to override it.
`--min-frame-interval SECONDS` changes the 30 s minimum; `--no-frames` skips Key frames.

## Check a Lecture note

```bash
lecture-notes verify note.md lecture-bundle          # add --json for machine-readable output
```

The Faithfulness check: every idea line in the note must cite a timestamp (`[12:34]`) or embed a Key frame (`![[frame_000754.jpg]]`) that really exists in the bundle. Exit code 0 means pass, 1 means problems, 2 means the note or bundle couldn't be read. See [docs/verify.md](docs/verify.md).

## Develop

```bash
python -m venv .venv && .venv/bin/pip install -e '.[whisper]' --group dev
.venv/bin/mypy && .venv/bin/pytest          # fast tests (fake transcriber)
.venv/bin/pytest -m slow                    # real faster-whisper; needs espeak-ng
```
