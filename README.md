# lecture-notes

Turn recorded lectures into faithful, timestamped text that a human or an agent can read and check.

> Early development. See the [spec](https://github.com/Silvelle/lecture-notes-skill/issues/1).

## Install

Requires Python ≥ 3.11 and [ffmpeg](https://ffmpeg.org) on `PATH`. For YouTube, yt-dlp also needs a JavaScript runtime: install [deno](https://deno.land) (node or bun work too). `lecture-notes doctor` shows what's missing.

```bash
pip install 'lecture-notes[whisper]'
```

## Use

```bash
lecture-notes extract "https://www.youtube.com/watch?v=…" -o lecture-bundle
lecture-notes extract lecture.mp4 -o lecture-bundle
```

Any URL [yt-dlp supports](https://github.com/yt-dlp/yt-dlp/blob/master/supportedsites.md) works; YouTube and local files are the tested Sources. Start-time parameters (`&t=…`) are ignored, a video picked from a playlist is taken on its own, and a playlist URL is refused (one Lecture per run).

This writes a **Lecture bundle**:

- `manifest.json`: Source, duration, language, Transcript origin, model, device, tool version, and the Key frame list
- `transcript.json`: timestamped segments (`start`, `end`, `text`) in the spoken language
- `transcript.md`: the Transcript as readable paragraphs with timestamps
- `frames/frame_<seconds>.jpg`: Key frames wherever the shown content changes (near-duplicates removed), plus at least one every 30 s

The language is detected automatically; pass `--lang ru` (or any code) to override it.
`--min-frame-interval SECONDS` changes the 30 s minimum; `--no-frames` skips Key frames.

## YouTube blocked me

YouTube sometimes answers "Sign in to confirm you're not a bot", especially on servers and VPNs. You can:

- pass `--cookies-from-browser firefox` (or `chrome`, `firefox:profile-name`, …) to use your logged-in session. Cookies are **never** read unless you pass this. Using them risks your Google account being flagged or banned, so prefer a secondary account.
- download the video another way and pass the local file.
- if only the video is blocked but subtitles are reachable, `extract` makes a transcript-only bundle on its own.

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
