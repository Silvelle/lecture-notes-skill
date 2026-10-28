# Lecture Notes

Turn a video lecture into Obsidian notes you can trust.

Give it a YouTube link or a video file. You get a note with the lecture's ideas. Every idea links to the second it was said. A checker makes sure of that, so nothing is made up.

Any subject works, not only programming: math, physics, chemistry, history, languages. Formulas become LaTeX, diagrams stay as images, slide text becomes text.

Works with Claude Code, Codex, Gemini CLI and Cursor. Runs on your computer. No API key.

## What you get

A note like this, in your Obsidian vault:

````markdown
---
title: Python basics
source: https://www.youtube.com/watch?v=VIDEO_ID
duration: 1:32:10
tags: [lecture, python]
---

# Python basics

## Conditions

- [[if]] runs a block only when its condition is true [12:34](https://www.youtube.com/watch?v=VIDEO_ID&t=754)
- The block is marked by indentation [12:50](https://www.youtube.com/watch?v=VIDEO_ID&t=770)

```python
if a == 1:
    print("one")
else:
    print("a is not 1")
```

- `else` handles every other case ![[attachments/python-basics/frame_000760.jpg]]
- [unclear: the formula on the board is out of focus] [15:02](https://www.youtube.com/watch?v=VIDEO_ID&t=902)
````

- **`[12:34]`** opens the video at that second. Click it to check.
- **The image** is the slide, saved from the video.
- **The code** is copied from the slide, not from the speech.
- **`[unclear]`** marks what couldn't be read. Nothing is guessed.

Want everything instead of a summary? Ask for the **full text**: every sentence in order, with slides and code in place.

## What you need

| | What | Why |
| - | ---- | --- |
| **Required** | Python 3.11 or newer | Runs the tool. |
| **Required** | [ffmpeg](https://ffmpeg.org) | Reads video and audio. |
| **For YouTube** | [deno](https://deno.land) | YouTube downloads need it. |
| **For notes** | An AI agent that can see images | Writes the note. Claude Code, Codex, Gemini CLI or Cursor. |
| Optional | [Obsidian](https://obsidian.md) | Notes are plain Markdown. Any editor opens them. |
| Optional | An NVIDIA GPU | About 5x faster than CPU. |

Disk space: the speech model takes 0.5-3 GB, downloaded once. A 1-hour video takes about 1 GB while it runs.

<details>
<summary><strong>How to install ffmpeg, deno and pipx</strong></summary>

| | Arch Linux | Ubuntu / Debian | macOS | Windows |
| - | ---------- | --------------- | ----- | ------- |
| ffmpeg | `sudo pacman -S ffmpeg` | `sudo apt install ffmpeg` | `brew install ffmpeg` | `winget install ffmpeg` |
| deno | `sudo pacman -S deno` | `curl -fsSL https://deno.land/install.sh \| sh` | `brew install deno` | `winget install deno` |
| pipx | `sudo pacman -S python-pipx` | `sudo apt install pipx` | `brew install pipx` | `py -m pip install --user pipx` |

After installing pipx, run `pipx ensurepath` once and open a new terminal.

</details>

## Install

### 1. Install the tool

```bash
pipx install 'lecture-notes[whisper]'
```

`pip` and `uvx` work too.

<details>
<summary><strong>Optional extras</strong></summary>

| Extra | Adds |
| ----- | ---- |
| `whisper` | Speech recognition on your computer. Recommended. |
| `ru` | A better model for Russian lectures. |
| `ocr` | Slide text without an agent. Also install `tesseract-ocr`. |

Combine them: `pipx install 'lecture-notes[whisper,ru,ocr]'`.

</details>

### 2. Add the skill to your agent

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

Or copy the `skills/lecture-notes/` folder into your agent's skills folder.

</details>

### 3. Check that everything is ready

```bash
lecture-notes doctor
```

It shows what it found and what is missing, with the command to fix it.

## Your first note

1. Open Claude Code and type:

   ```text
   /lecture-notes:lecture-notes https://www.youtube.com/watch?v=VIDEO_ID
   ```

2. **First time only:** it asks where your Obsidian vault is. Answer with a folder, like `~/Obsidian/Lectures`. It remembers.
3. **It shows a plan:** the title, the length, and how long it will take. On a slow computer it asks before starting.
4. **Wait.** It downloads the video, writes the note, and checks it.
5. **Open the note** in Obsidian. Click a few timestamps to see that they match.

`VIDEO_ID` stands for the part after `v=` in a YouTube link. Not sure what to type? Run `/lecture-notes:lecture-notes help`.

## Examples

Ask in plain words. There is no fixed syntax.

| You type | You get |
| -------- | ------- |
| `/lecture-notes:lecture-notes https://www.youtube.com/watch?v=VIDEO_ID` | A note in the lecture's language |
| `/lecture-notes:lecture-notes https://youtu.be/VIDEO_ID full text` | Everything said, with slides in place |
| `/lecture-notes:lecture-notes ~/Videos/lecture.mp4` | A note from a video on your disk |
| `/lecture-notes:lecture-notes https://www.youtube.com/watch?v=VIDEO_ID in English` | The note in English; code stays as is |
| `/lecture-notes:lecture-notes https://www.youtube.com/watch?v=VIDEO_ID into ~/Notes/Physics` | The note in another folder, this time only |
| `/lecture-notes:lecture-notes https://www.youtube.com/watch?v=VIDEO_ID, use firefox` | Uses your Firefox login if YouTube blocks |
| `/lecture-notes:lecture-notes help` | A short usage card |

You can also just write: "make notes from this lecture: https://www.youtube.com/watch?v=VIDEO_ID".

In Claude Code, a skill from a plugin starts with the plugin's name, so the command is `/lecture-notes:lecture-notes`. If you copied the skill into `~/.claude/skills/` instead, it is just `/lecture-notes`.

## Workflows

### Everything that was said

1. Type `/lecture-notes:lecture-notes https://www.youtube.com/watch?v=VIDEO_ID full text`.
2. You get every sentence in order. Code and formulas are copied from the slides.
3. The checker makes sure nothing was added and nothing was left out.

### A video you already have

1. Type `/lecture-notes:lecture-notes ~/Videos/lecture.mp4`.
2. Timestamps in the note show as `[12:34]`, without a link.

### Without any AI agent

1. Run:

   ```bash
   lecture-notes extract "https://www.youtube.com/watch?v=VIDEO_ID" -o my-lecture
   ```

2. Open `my-lecture/transcript.md`. It is the full text, with each slide image where it appeared.
3. The slide images are also in `my-lecture/frames/`.

With the `ocr` extra, the text of each slide appears under its image too.

### A Russian lecture

1. Install the Russian extra:

   ```bash
   pipx install --force 'lecture-notes[whisper,ru]'
   ```

2. Ask as usual. Add `in Russian` if the video doesn't say its language.
3. Code and English terms stay exactly as spoken.

### A long lecture on a laptop

1. See the estimate first:

   ```bash
   lecture-notes extract ~/Videos/lecture.mp4 --plan
   ```

2. Too slow? Try a 5-minute piece:

   ```bash
   ffmpeg -ss 00:10:00 -t 300 -i lecture.mp4 -c copy clip.mp4
   ```

3. Or allow YouTube's own captions: add `--allow-auto-subs`. Faster, but code comes out garbled.

### Check a note yourself

```bash
lecture-notes verify "~/Obsidian/Lectures/Python basics.md" ~/Obsidian/Lectures/.lecture-bundles/python-basics
```

It lists every idea without a link, every wrong timestamp and every unknown image.

## When something goes wrong

**YouTube says "confirm you're not a bot".**
This happens most on servers and VPNs. You can:

- Add `use firefox` (or your browser) to the request. It uses your browser login. Your account could get flagged, so a spare account is safer.
- Download the video yourself and give the file:

  ```bash
  yt-dlp --cookies-from-browser firefox -o lecture.mp4 "https://www.youtube.com/watch?v=VIDEO_ID"
  ```

**It's very slow.**
It runs on your CPU. Run `lecture-notes doctor` to see why. With an NVIDIA GPU, it may only need its libraries:

```bash
pipx inject lecture-notes nvidia-cublas-cu12 nvidia-cudnn-cu12
```

**"speech recognition needs faster-whisper".**
Install the tool with the `whisper` extra: `pipx install --force 'lecture-notes[whisper]'`.

**The language is wrong.**
Say it in the request: `in Russian`, `in German`. Or pass `--lang ru` to `extract`.

**Where are my files?**

- The note: `<vault>/<title>.md`.
- Its slide images: `<vault>/attachments/<lecture>/`.
- The raw transcript and frames: `<vault>/.lecture-bundles/<lecture>/`. Obsidian hides this folder.

**I want another vault.**

```bash
lecture-notes config vault ~/Obsidian/Lectures
```

## Why you can trust the note

- **Only from the lecture.** Every fact comes from what was said or shown. Nothing from the AI's own knowledge.
- **Every idea has a link.** Each one points to the second it was said, or to the slide it was on.
- **Checked by a program.** `verify` tests every link against the lecture. The skill only finishes when it passes.
- **No guessing.** Unreadable parts are marked `[unclear]`.
- **Code from the screen.** Code and formulas are copied from the slide images. Spoken code is often garbled: `else: print("a is not 1")` becomes "els Принт А из нот единица".

The checker can't confirm that a sentence matches its moment word for word. Clicking a few timestamps is still a good habit.

## Reference

<details>
<summary><strong>Commands</strong></summary>

```bash
lecture-notes extract "https://www.youtube.com/watch?v=VIDEO_ID" -o my-lecture
lecture-notes extract lecture.mp4 --plan      # what it would do; downloads nothing
lecture-notes verify note.md my-lecture       # check a note
lecture-notes verify note.md my-lecture --full  # also check nothing is left out
lecture-notes config vault ~/Obsidian/Lectures
lecture-notes doctor
```

`verify` exits 0 when the note passes, 1 when it has problems, 2 when it can't read the files. Details: [docs/verify.md](docs/verify.md).

</details>

<details>
<summary><strong>extract options</strong></summary>

| Option | What it does |
| ------ | ------------ |
| `-o <folder>` | Where to put the results. |
| `--lang ru` | Set the language. |
| `--model`, `--device` | Pick the speech model yourself. |
| `--backend` | `faster-whisper` or `onnx-asr`. |
| `--yes` | Don't ask before long jobs. |
| `--allow-auto-subs` | Use YouTube's auto-captions. |
| `--no-frames` | Text only, no slide images. |
| `--min-frame-interval 30` | Save a frame at least this often. |
| `--cookies-from-browser firefox` | Use your browser login. |
| `--plan` | Show the plan as JSON; download nothing. |

</details>

<details>
<summary><strong>Where the text comes from</strong></summary>

Best first:

1. Subtitles written by people.
2. Speech recognition on your computer.
3. YouTube's auto-captions, only as a last resort.

The file `manifest.json` records which one was used.

</details>

<details>
<summary><strong>Speed</strong></summary>

| Your computer | Model | Time for 1 hour of video |
| ------------- | ----- | ------------------------ |
| GPU, 8 GB+ free | large-v3 | ~5 min |
| GPU, 5-8 GB | large-v3-turbo | ~3 min |
| GPU, 3-5 GB | medium | ~3 min |
| GPU, under 3 GB | small | ~2 min |
| CPU only | small | ~25 min |
| Russian, `ru` extra | GigaAM v3 | ~6 min on CPU |

These are estimates from benchmarks. Measured numbers are coming.

</details>

<details>
<summary><strong>How it works</strong></summary>

1. `extract` downloads the video. It saves the transcript and an image at each slide change.
2. The agent reads all of it, including the images.
3. The agent writes a [note](skills/lecture-notes/note-format.md) or the [full text](skills/lecture-notes/full-text-format.md).
4. `verify` checks it. The agent fixes problems until it passes.

The tool itself never calls an AI service ([ADR-0001](docs/adr/0001-no-llm-calls-in-package.md)). Only the agent writes.

</details>

## For developers

```bash
python -m venv .venv && .venv/bin/pip install -e '.[whisper]' --group dev
.venv/bin/mypy && .venv/bin/pytest
```

See [CONTRIBUTING.md](CONTRIBUTING.md). MIT [license](LICENSE).
