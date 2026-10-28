# Full text format

The whole Lecture as one Markdown page for Obsidian: everything said, in order, with everything shown placed where it appeared. `lecture-notes verify --full` checks it, including that no stretch of speech is left out.

## Frontmatter

The same fields as a Lecture note (see [note-format.md](note-format.md)), with `transcript` in the tags.

## Body

- `# <title>`. Add `##` headings where the Lecture moves to a new topic.
- **Every sentence of the Transcript, in order.** Keep the lecturer's words. Drop only filler (э-э, um, ну), false starts and stutters.
- **One paragraph per line.** Start a paragraph where `transcript.md` does, and end it with the paragraph's timestamp: `[12:34](<source URL>&t=754)` for URL Sources, `[12:34]` for local files.
- Fix obvious recognition errors to what was clearly meant: "pie torch" becomes PyTorch, "Принт" becomes `print`.

## What was shown

At the point where each Key frame appears in `transcript.md`, put the frame on its own line, then its Board content, copied from the image (never from OCR text or the speech):

- **The frame**: `![[attachments/<short-name>/frame_000754.jpg]]`.
- **Code**: a fenced block with its language, exactly as on screen.
- **Formulas**: a `$$` block in LaTeX.
- **Slide text**: one line, `Slide: <the text> [12:34]`.
- **Diagrams and structures**: the frame alone, plus a line with their visible labels and the timestamp.

Skip a frame that repeats the previous one or shows only the lecturer.

## Faithfulness

- Nothing added: no summaries, explanations or headings that claim more than the Lecture says.
- Nothing left out: when unsure whether a sentence matters, keep it.
- Where speech is inaudible or a frame unreadable: `[unclear: reason] [12:34]` on its own line.
- Text in the note language (the Lecture's, unless the user asked to translate). Code, identifiers and terms stay exactly as spoken or shown.

## Example

````markdown
---
title: Python basics
source: https://www.youtube.com/watch?v=1GLDLn-HQe8
channel: MEPhI
date: 2026-10-28
duration: 2:42:10
language: ru
tags: [lecture, transcript, python]
---

# Python basics

## Условия

Сейчас посмотрим на условный оператор. Если a равно единице, печатаем «one». [12:34](https://www.youtube.com/watch?v=1GLDLn-HQe8&t=754)

![[attachments/python-basics/frame_000760.jpg]]

```python
if a == 1:
    print("one")
else:
    print("a is not 1")
```

Иначе срабатывает ветка else, и мы печатаем, что a не единица. [12:50](https://www.youtube.com/watch?v=1GLDLn-HQe8&t=770)
````
