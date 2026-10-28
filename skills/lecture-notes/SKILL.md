---
name: lecture-notes
description: Turn a video lecture (YouTube or any yt-dlp URL, or a local video file) into one faithful Obsidian Lecture note where every idea cites a timestamp or Key frame, checked by `lecture-notes verify`; or into its full text with the slides, code and formulas in place. Use when the user wants notes, a summary, a transcript or the full text of a lecture, talk, class or course video.
license: MIT
compatibility: Needs the `lecture-notes` CLI (pip install 'lecture-notes[whisper]'), ffmpeg, and a JS runtime such as deno for YouTube. The agent must be able to view images.
---

# Lecture notes

You turn one Lecture into one Lecture note, or into its full text. The `lecture-notes` CLI does the extraction; you do the writing; `verify` checks your writing against the Lecture bundle. The note is **faithful**: it holds only what the Lecture says or shows, and every idea carries a Citation.

## 1. Read the request

The user writes in plain words; there is no fixed syntax. Pick out:

- **Source**: a URL or a video file path. Required.
- **Vault**: the folder notes go to ("into ~/Obsidian/Lectures", "vault X").
- **Mode**: **note** (default: the ideas, grouped by topic) or **full** ("full text", "transcript", "everything", "word for word": everything said, in order, with what was shown in place).
- **Language** of the note ("in English"). Default: the Lecture's language.

If the request is empty or asks for help, show the user the Usage card at the end of this file, as written, and stop. If only the Source is missing, ask for it.

## 2. Check the tool

Run `lecture-notes doctor`. If the command is missing, install it with `pip install 'lecture-notes[whisper]'`. If `doctor` reports ffmpeg missing, or the JS runtime missing for a YouTube Source, tell the user what to install and stop.

## 3. Find the vault

If the user named a vault, use it. Otherwise run `lecture-notes config vault`: it prints the remembered vault, or exits 1 when none is set. With none set, ask the user where their notes should go, save the answer with `lecture-notes config vault "<folder>"`, and tell them it will be reused.

The bundle goes to `<vault>/.lecture-bundles/<short-name>`, where `<short-name>` is the title in lowercase words joined by `-`.

## 4. Show the plan

```bash
lecture-notes extract "<source>" -o "<vault>/.lecture-bundles/<short-name>" --plan
```

It prints JSON and downloads nothing. Show the user this summary, filled from it:

```text
Lecture:  <title> (<duration as h:mm:ss>)
Note:     <vault>/<title>.md  (<mode>, <language>)
Text:     <transcript_origin in words>, <model> on <device>, about <estimate> min
```

Then go straight on, unless:

- `needs_confirmation` is true: a long job on the CPU. Ask whether to go ahead; on yes, add `--yes` in step 5.
- `transcript_origin` is null: no Transcript is possible here. Tell the user why (the `doctor` output says what is missing) and stop.
- The command fails as **blocked by the site**: relay the listed ways out and stop. Pass `--cookies-from-browser` only when the user names a browser.

## 5. Extract the Lecture bundle

```bash
lecture-notes extract "<source>" -o "<vault>/.lecture-bundles/<short-name>"
```

Done when it prints the bundle folder.

## 6. Read the whole bundle

- `manifest.json`: title, Source URL, channel, duration, language, `transcript_origin`, and the Key frame list.
- `transcript.md`: the full Transcript with timestamps, each Key frame where it appeared. Read all of it.
- Every image in `frames/`: open each one. Key frames carry the Board content (code, slides, formulas, diagrams) that speech alone garbles.

Done when you have read the Transcript end to end and looked at every Key frame.

## 7. Write the note

For **note** mode, read [note-format.md](note-format.md) now and follow it: frontmatter, topics, Citation forms, Board content, Unclear markers, language.

For **full** mode, read [full-text-format.md](full-text-format.md) now and follow it. Work through `transcript.md` from top to bottom.

Write the note to `<vault>/<title>.md`, with `/ \ : * ? " < > |` in the title replaced by `-`. Copy each Key frame you embed from `<bundle>/frames/` into `<vault>/attachments/<short-name>/`, so frames of different Lectures never collide, and embed them by that path.

## 8. Verify until it passes

```bash
lecture-notes verify "<vault>/<title>.md" "<bundle>" --json          # note mode
lecture-notes verify "<vault>/<title>.md" "<bundle>" --json --full   # full mode
```

Fix every reported problem at its line, using the `suggestion`, and run `verify` again. `uncovered_speech` (line 0) names a stretch of the Lecture the full text leaves out: add it. Done only when `verify` exits 0. Exit code 2 means the note or bundle path is wrong.

## 9. Report

Tell the user where the note is, that `verify` passed, where the Transcript came from, and every place you marked `[unclear]`.

## Usage card

```text
Lecture notes: faithful Obsidian notes from a video lecture.

  /lecture-notes <link or video file>
  /lecture-notes <link> full text
  /lecture-notes <file> into ~/Obsidian/Lectures, in English
  /lecture-notes help

  Notes go to your vault: asked once, then remembered.
  Change it: lecture-notes config vault <folder>

  Every idea links to its moment in the video,
  and a checker makes sure of it.
  "full text" gives everything that was said,
  with slides and code in place.

  YouTube wants a login? Say which browser to use
  ("use firefox"), or download the video and give the file.
```
