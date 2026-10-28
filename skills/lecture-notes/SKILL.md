---
name: lecture-notes
description: Turn a video lecture (YouTube or any yt-dlp URL, or a local video file) into one faithful Obsidian Lecture note where every idea cites a timestamp or Key frame, checked by `lecture-notes verify`; or into its full text with the slides, code and formulas in place. Use when the user wants notes, a summary, a transcript or the full text of a lecture, talk, class or course video.
license: MIT
compatibility: Needs the `lecture-notes` CLI (pip install 'lecture-notes[whisper]'), ffmpeg, and a JS runtime such as deno for YouTube. The agent must be able to view images.
---

# Lecture notes

You turn one Lecture into one Lecture note, or into its full text. The `lecture-notes` CLI does the extraction; you do the writing; `verify` checks your writing against the Lecture bundle. The note is **faithful**: it holds only what the Lecture says or shows, and every idea carries a Citation.

Inputs from the user: the **Source** (URL or file path), optionally a **vault folder** (default: the current folder), a **note language** (default: the Lecture's language) and the **mode**:

- **note** (default): the Lecture's ideas, grouped by topic.
- **full**: everything said, in order, with what was shown placed where it appeared. Use it when the user asks for the full text, a transcript, or "everything".

## 1. Check the tool

Run `lecture-notes doctor`. If the command is missing, install it with `pip install 'lecture-notes[whisper]'`. If `doctor` reports ffmpeg missing, or the JS runtime missing for a YouTube Source, tell the user what to install and stop.

## 2. Extract the Lecture bundle

```bash
lecture-notes extract "<source>" -o "<vault>/.lecture-bundles/<short-name>"
```

Done when it prints the bundle folder. Two stops hand the decision to the user:

- **Long CPU job.** `extract` stops and asks for `--yes`, showing an estimate. Relay the estimate; rerun with `--yes` only after the user agrees, or with `--allow-auto-subs` if they prefer speed over accuracy.
- **Blocked by the site.** Relay the listed ways out. Browser cookies are the user's call: pass `--cookies-from-browser` only when the user names a browser.

## 3. Read the whole bundle

- `manifest.json`: title, Source URL, channel, duration, language, `transcript_origin`, and the Key frame list.
- `transcript.md`: the full Transcript with timestamps. Read all of it.
- Every image in `frames/`: open each one. Key frames carry the Board content (code, slides, formulas, diagrams) that speech alone garbles.

Done when you have read the Transcript end to end and looked at every Key frame.

## 4. Write the Lecture note

For **note** mode, read [note-format.md](note-format.md) now and follow it: frontmatter, topics, Citation forms, Board content, Unclear markers, language.

For **full** mode, read [full-text-format.md](full-text-format.md) now and follow it. Work through `transcript.md` from top to bottom: it already has each Key frame where it appeared.

Write the note to `<vault>/<title>.md`, with `/ \ : * ? " < > |` in the title replaced by `-`. Copy each Key frame you embed from `<bundle>/frames/` into `<vault>/attachments/<short-name>/` (the same short name as the bundle), so frames of different Lectures never collide, and embed them by that path.

## 5. Verify until it passes

```bash
lecture-notes verify "<vault>/<title>.md" "<bundle>" --json          # note mode
lecture-notes verify "<vault>/<title>.md" "<bundle>" --json --full   # full mode
```

Fix every reported problem at its line, using the `suggestion`, and run `verify` again. `uncovered_speech` (line 0) names a stretch of the Lecture the full text leaves out: add it. Done only when `verify` exits 0. Exit code 2 means the note or bundle path is wrong.

## 6. Report

Tell the user where the note is, that `verify` passed, the Transcript origin from the Manifest, and every place you marked `[unclear]`.
