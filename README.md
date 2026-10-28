# Lecture Notes

Faithful, cited Obsidian notes from any video lecture.

Give it a YouTube link or a video file. You get one Obsidian note. Every idea in it points to the second it was said or the frame it was shown. A program checks that, so nothing made up gets through.

It works with Claude Code, Codex, Gemini CLI, Cursor and any agent that reads `SKILL.md`. No API key. No cloud transcription.

## Installation (2-minute setup)

### 1. Install the CLI

```bash
pipx install 'lecture-notes[whisper]'
```

You also need [ffmpeg](https://ffmpeg.org). For YouTube, install [deno](https://deno.land) too.

<details>
<summary><strong>Extras</strong></summary>

| Extra | Adds |
| ----- | ---- |
| `whisper` | Local speech recognition (faster-whisper). Recommended. |
| `ru` | GigaAM v3 for Russian lectures (onnx-asr). |
| `ocr` | Text from slides and boards (tesseract). Also install `tesseract-ocr`. |

Combine them: `pipx install 'lecture-notes[whisper,ru,ocr]'`.

</details>

### 2. Get the skill

<details>
<summary><strong>Claude Code</strong></summary>

```text
/plugin install lecture-notes --marketplace Silvelle/lecture-notes-skill
```

On older versions:

```text
/plugin marketplace add Silvelle/lecture-notes-skill
/plugin install lecture-notes@lecture-notes
```

</details>

<details>
<summary><strong>Codex</strong></summary>

```bash
codex plugin marketplace add Silvelle/lecture-notes-skill
codex plugin add lecture-notes@lecture-notes
```

</details>

<details>
<summary><strong>Gemini CLI</strong></summary>

```bash
gemini skills install https://github.com/Silvelle/lecture-notes-skill.git --path skills/lecture-notes
```

</details>

<details>
<summary><strong>Cursor and other agents</strong></summary>

```bash
npx skills@latest add Silvelle/lecture-notes-skill -a cursor
```

Or copy `skills/lecture-notes/` into your agent's skills folder.

</details>

### 3. Check your machine

```bash
lecture-notes doctor
```

It shows your hardware, the model it will use, and anything missing.

## Why Lecture Notes

### #1: Auto-captions garble code

**The Problem.** Code read aloud becomes nonsense. `else: print("a is not 1")` turns into "els Принт А из нот единица". Formulas and slides are not spoken at all.

**The Fix.** Human subtitles come first. Otherwise a local speech model runs. Key frames capture every slide change. The agent copies code from the frame, not from the speech.

### #2: AI summaries invent things

**The Problem.** A summary reads well. But some of it the lecturer never said. You can't tell which part.

**The Fix.** Every idea carries a Citation: a timestamp or a Key frame. `lecture-notes verify` checks each one against the bundle. The skill only finishes when `verify` passes. Unreadable parts get an `[unclear]` marker instead of a guess.

### #3: Transcription freezes the laptop

**The Problem.** A big model on a weak machine runs for hours at full fan.

**The Fix.** The tool picks a model for your hardware. It shows an estimate first. On CPU it asks before a long job. It leaves half your cores free.

## How it works

```text
Source ──extract──▶ Lecture bundle ──agent──▶ Lecture note ──verify──▶ pass
(URL/file)          transcript + frames       (Obsidian)              (exit 0)
```

1. `extract` builds the **Lecture bundle**: `manifest.json`, `transcript.json`, `transcript.md` and `frames/`.
2. The agent reads all of it, including every Key frame image.
3. The agent writes one note in [this format](skills/lecture-notes/note-format.md).
4. `verify` checks every Citation. The agent fixes and re-runs until it passes.

The package itself never calls an LLM ([ADR-0001](docs/adr/0001-no-llm-calls-in-package.md)). Without an agent you still get the full transcript and the frames.

## The CLI

```bash
lecture-notes extract "https://www.youtube.com/watch?v=…" -o bundle
lecture-notes extract lecture.mp4 -o bundle
lecture-notes verify note.md bundle --json
lecture-notes doctor
```

<details>
<summary><strong>extract options</strong></summary>

| Option | What it does |
| ------ | ------------ |
| `--lang ru` | Set the spoken language instead of detecting it. |
| `--model`, `--device` | Override the automatic model choice. |
| `--backend` | `faster-whisper` or `onnx-asr`. |
| `--yes` | Skip the question before a long CPU job. |
| `--allow-auto-subs` | Use the site's auto-captions instead of local recognition. |
| `--no-frames` | Transcript only. |
| `--min-frame-interval 30` | At least one Key frame this often. |
| `--cookies-from-browser firefox` | Use your browser login. See below. |

</details>

**Where the transcript comes from**, best first:

1. Human-written subtitles.
2. Local speech recognition.
3. Auto-generated subtitles, only when allowed or when nothing else works.

The Manifest records which one was used.

**`verify`** exits 0 on pass, 1 on problems, 2 if it can't read the files. The rules and JSON format are in [docs/verify.md](docs/verify.md).

## Requirements & performance

Python 3.11 or newer, ffmpeg, and deno for YouTube.

| Your machine | Model | Rough speed for 1 hour of audio |
| ------------ | ----- | ------------------------------- |
| GPU, 8 GB+ free | large-v3, float16 | ~5 min |
| GPU, 5-8 GB | large-v3-turbo, float16 | ~3 min |
| GPU, 3-5 GB | medium, float16 | ~3 min |
| CPU only | small, int8 | ~25 min |
| Russian + `[ru]` extra | GigaAM v3 | ~6 min on CPU |

These are estimates from the backends' benchmarks. Measured numbers are coming. RTX 50-series cards always use float16.

## YouTube blocked me

YouTube sometimes says "Sign in to confirm you're not a bot". This happens most on servers and VPNs. You have three ways out:

- **Use your browser login.** Pass `--cookies-from-browser firefox` (or `chrome`, `firefox:profile`). Cookies are never read without this flag. Your Google account could get flagged. Use a second account if you can.
- **Use a local file.** Download the video another way and pass the file.
- **Take the transcript only.** If only the video is blocked, `extract` makes a transcript-only bundle on its own.

## How it differs

- **Checked, not promised.** `verify` tests every Citation against the lecture.
- **Board content.** Code, slides and formulas come from Key frames, not speech.
- **Any language.** Mixed Russian and English works. Code is never translated.
- **Safe defaults.** Fits the model to your machine. Asks before long CPU jobs.
- **Obsidian native.** Frontmatter, `[[links]]`, embedded frames.

## Develop

```bash
python -m venv .venv && .venv/bin/pip install -e '.[whisper]' --group dev
.venv/bin/mypy && .venv/bin/pytest
```

See [CONTRIBUTING.md](CONTRIBUTING.md).

## Use it as a Claude skill

After step 2, ask your agent in plain words:

> Make notes from https://www.youtube.com/watch?v=1GLDLn-HQe8

Or call the skill directly. In Claude Code, a skill from a plugin carries the plugin's name:

```text
/lecture-notes:lecture-notes https://www.youtube.com/watch?v=1GLDLn-HQe8
/lecture-notes:lecture-notes ~/Videos/lecture.mp4 vault ~/Obsidian/Lectures
/lecture-notes:lecture-notes https://youtu.be/… in English
```

If you copied the skill into `~/.claude/skills/` instead, it is just `/lecture-notes`.

The skill runs `extract`, reads the bundle, writes the note into your vault, and runs `verify` until it passes. It stops and asks you before a long CPU job or before using browser cookies.
