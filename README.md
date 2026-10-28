# Lecture Notes

Faithful, cited Obsidian notes from any video lecture.

Give it a YouTube link or a video file. Get one Obsidian note. Every idea links to its second in the video. A program checks each link.

Works with Claude Code, Codex, Gemini CLI and Cursor. No API key. No cloud.

## Installation (2-minute setup)

### 1. Install the CLI

```bash
pipx install 'lecture-notes[whisper]'
```

`pip` and `uvx` work too. You also need [ffmpeg](https://ffmpeg.org). For YouTube, add [deno](https://deno.land).

<details>
<summary><strong>Extras</strong></summary>

| Extra | Adds |
| ----- | ---- |
| `whisper` | Local speech recognition. Recommended. |
| `ru` | GigaAM v3 for Russian lectures. |
| `ocr` | Text from slides. Needs `tesseract-ocr`. |

Combine: `pipx install 'lecture-notes[whisper,ru,ocr]'`.

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

Or copy `skills/lecture-notes/` to your skills folder.

</details>

### 3. Check your machine

```bash
lecture-notes doctor
```

Shows your hardware, the chosen model, and what's missing.

## Why Lecture Notes

### #1: Auto-captions garble code

**The Problem.** Spoken code turns to nonsense. `else: print("a is not 1")` becomes "els Принт А из нот единица". Slides are never spoken.

**The Fix.** Human subtitles first, then a local model. Every slide change is saved as a Key frame. Code is copied from the frame.

### #2: AI summaries invent things

**The Problem.** A summary reads well. Some of it was never said. You can't tell which part.

**The Fix.** Every idea cites a timestamp or a Key frame. `verify` checks each one. The skill stops only when it passes. Unreadable parts get `[unclear]`, not a guess.

### #3: Transcription freezes the laptop

**The Problem.** A big model on a weak laptop runs for hours.

**The Fix.** The model fits your hardware. You see an estimate first. Long CPU jobs ask first. Half your cores stay free.

## How it works

```text
Source ──extract──▶ Lecture bundle ──agent──▶ Lecture note ──verify──▶ pass
(URL/file)          transcript + frames       (Obsidian)              (exit 0)
```

1. `extract` builds the **Lecture bundle**: transcript, frames, manifest.
2. The agent reads it all, images too.
3. The agent writes a [note](skills/lecture-notes/note-format.md) or the [full text](skills/lecture-notes/full-text-format.md).
4. `verify` checks it. The agent fixes until it passes.

The CLI never calls an LLM ([ADR-0001](docs/adr/0001-no-llm-calls-in-package.md)).

**No agent? You still get the whole Lecture.** `transcript.md` is the full text with each slide in place. With `ocr`, slide text sits under each image.

## The CLI

```bash
lecture-notes extract "https://www.youtube.com/watch?v=…" -o bundle
lecture-notes extract lecture.mp4 -o bundle
lecture-notes verify note.md bundle --json
lecture-notes verify full-text.md bundle --full
lecture-notes doctor
```

<details>
<summary><strong>extract options</strong></summary>

| Option | What it does |
| ------ | ------------ |
| `--lang ru` | Set the language. |
| `--model`, `--device` | Pick the model yourself. |
| `--backend` | `faster-whisper` or `onnx-asr`. |
| `--yes` | Don't ask before long CPU jobs. |
| `--allow-auto-subs` | Use the site's auto-captions. |
| `--no-frames` | Transcript only. |
| `--min-frame-interval 30` | A frame at least this often. |
| `--cookies-from-browser firefox` | Use your browser login. |

</details>

**Where the transcript comes from**, best first:

1. Human-written subtitles.
2. Local speech recognition.
3. Auto-captions, as a last resort.

The Manifest records which one was used.

**`verify`** exits 0 on pass, 1 on problems, 2 on unreadable files. `--full` also flags missing speech. Details: [docs/verify.md](docs/verify.md).

## Requirements & performance

Python 3.11 or newer, ffmpeg, and deno for YouTube.

| Your machine | Model | Rough speed for 1 hour of audio |
| ------------ | ----- | ------------------------------- |
| GPU, 8 GB+ free | large-v3, float16 | ~5 min |
| GPU, 5-8 GB | large-v3-turbo, float16 | ~3 min |
| GPU, 3-5 GB | medium, float16 | ~3 min |
| GPU, under 3 GB | small, float16 | ~2 min |
| CPU only | small, int8 | ~25 min |
| Russian + `[ru]` extra | GigaAM v3 | ~6 min on CPU |

Estimates from benchmarks; measured numbers coming. RTX 50-series uses float16.

## YouTube blocked me

YouTube sometimes asks you to "confirm you're not a bot". Mostly on servers and VPNs. Three ways out:

- **Use your browser login.** Pass `--cookies-from-browser firefox`. Cookies are never read without it. Your account could get flagged. Use a spare one.
- **Use a local file.** Download the video yourself.
- **Take the transcript only.** If only the video is blocked, you still get the text.

## How it differs

- **Checked, not promised.** `verify` tests every Citation.
- **Board content.** Code and formulas come from the frames.
- **Any language.** Mixed Russian and English works.
- **Safe defaults.** Fits your machine. Asks before long jobs.
- **Obsidian native.** Frontmatter, `[[links]]`, embedded frames.

## Develop

```bash
python -m venv .venv && .venv/bin/pip install -e '.[whisper]' --group dev
.venv/bin/mypy && .venv/bin/pytest
```

See [CONTRIBUTING.md](CONTRIBUTING.md).

## Use it as a Claude skill

Ask your agent in plain words:

> Make notes from https://www.youtube.com/watch?v=1GLDLn-HQe8

Or call it directly. Plugin skills carry the plugin's name:

```text
/lecture-notes:lecture-notes https://www.youtube.com/watch?v=1GLDLn-HQe8
/lecture-notes:lecture-notes ~/Videos/lecture.mp4 vault ~/Obsidian/Lectures
/lecture-notes:lecture-notes https://youtu.be/… in English
```

Copied into `~/.claude/skills/`? Then it's just `/lecture-notes`.

**Want everything, not a summary?** Add `full`:

```text
/lecture-notes:lecture-notes https://www.youtube.com/watch?v=1GLDLn-HQe8 full
```

You get every sentence in order. Slides, code and formulas sit where they were shown. `verify --full` checks nothing was added or left out.

The skill extracts, writes, and verifies until it passes. It asks before long CPU jobs and before using cookies.
