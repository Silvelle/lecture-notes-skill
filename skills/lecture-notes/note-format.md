# Lecture note format

One Markdown note per Lecture, for Obsidian. `lecture-notes verify` checks it.

## Frontmatter

```yaml
---
title: <Lecture title from the Manifest>
source: <Manifest source.url, or the local file path>
channel: <Manifest channel, or the lecturer if the Lecture names one>
date: <today, YYYY-MM-DD>
duration: <h:mm:ss from the Manifest duration>
language: <note language code>
tags: [lecture, <2-4 topic tags>]
---
```

## Body

- `# <title>`, then one `##` heading per topic, in the order the Lecture covers them.
- Under each topic, short bullets: one idea per bullet, in your own words, ending with its Citation.
- `[[Concept]]` links on the key concepts, so the same concept connects across Lectures. Link the concept's name as the Lecture says it.
- A Mermaid concept map (` ```mermaid `) under `## Concept map` only when the Lecture builds ideas on each other; most Lectures need none.

The note holds the Lecture's ideas and nothing else: no questions, flashcards, exercises or summaries of your own.

## Citations

Every idea line ends with at least one Citation:

- URL Source: `[12:34](<source URL>&t=754)`. The `t=` value is the label in seconds. For `youtu.be` links use `?t=754`.
- Local file: `[12:34]`.
- A Key frame embed also counts: `![[frame_000754.jpg]]`.

Cite the start of the Transcript segment the idea comes from (or the Key frame's time). Use `[h:mm:ss]` past the first hour.

## Board content

Transcribe what is shown from the Key frames, never from the speech alone:

- **Code**: a fenced block with its language (` ```python `), copied exactly as on screen, then a bullet that cites it.
- **Formulas**: LaTeX, `$...$` inline or a `$$` block.
- **Slide text**: bullets, cited.
- **Diagrams, chemical structures, plots**: embed the Key frame (`![[frame_000754.jpg]]`) and write only the labels visible in it.

## Faithfulness

- Use only the bundle: the Transcript and the Key frames. Every fact, name and number comes from there.
- Fix obvious transcription errors to what was clearly meant: "pie torch" becomes PyTorch, "Принт" becomes `print`. Reordering for clarity is fine.
- Keep the lecturer's claims as stated, including ones you believe are wrong.
- Where speech is inaudible or the board unreadable, write an Unclear marker on its own bullet with a Citation: `- [unclear: board out of focus] [12:34]`.

## Language

Write in the note language: the Lecture's language unless the user asked for another. Code, identifiers, commands and technical terms stay exactly as spoken or shown.

## Example

````markdown
---
title: Python basics
source: https://www.youtube.com/watch?v=1GLDLn-HQe8
channel: MEPhI
date: 2026-10-28
duration: 2:42:10
language: ru
tags: [lecture, python, control-flow]
---

# Python basics

## Условия

- [[if]] проверяет условие; блок выделяется отступом [12:34](https://www.youtube.com/watch?v=1GLDLn-HQe8&t=754)

```python
if a == 1:
    print("one")
else:
    print("a is not 1")
```

- Пример с `else` на слайде ![[frame_000760.jpg]]
- [unclear: формула на доске не читается] [1:05:12](https://www.youtube.com/watch?v=1GLDLn-HQe8&t=3912)
````
