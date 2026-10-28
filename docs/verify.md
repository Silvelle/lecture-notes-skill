# `verify`: the Faithfulness check

```bash
lecture-notes verify <note.md> <bundle> [--json]
```

Checks a Lecture note against its Lecture bundle: every idea must carry a Citation, and every Citation must point at something that is really in the bundle.

## Exit codes

| Code | Meaning |
| ---- | ------- |
| 0 | Pass: every idea has a Citation that matches the bundle |
| 1 | The note has problems (listed in the output) |
| 2 | The note or the bundle could not be read; nothing was checked |

## What counts as an idea

Every non-blank line of the note is an idea line (bullets, numbered items, paragraphs, quotes, table rows), except:

- the YAML frontmatter at the top (`---` … `---`)
- fenced blocks: code and Mermaid (```` ``` ```` or `~~~`)
- display math: `$$` … `$$` blocks and one-line `$$ … $$`
- comments: `<!-- … -->` and Obsidian `%% … %%`
- headings (`# Title`, and setext titles underlined with `===` or `---`), callout headers (`> [!note] Title`), horizontal rules, and table header and separator rows

`#tag` (no space after `#`) is not a heading, so a line starting with a tag is an idea. Code indented by four spaces is not recognised as code; use fenced blocks.

Inline code is ignored when looking for Citations, so `` `a[1:23]` `` is not a timestamp.

## Citations

An idea line is cited when it contains at least one of:

- a timestamp: `[12:34]` or `[1:02:05]`
- a linked timestamp: `[12:34](https://www.youtube.com/watch?v=…&t=754)`. The link's `t=` may be `754`, `754s` or `12m34s`
- an embedded Key frame: `![[frame_000754.jpg]]`, `![[attachments/frame_000754.jpg|400]]` or `![alt](frames/frame_000754.jpg)`. Only the file name is compared, so any attachments folder works

Both timestamp forms are accepted for any Source. `[[00:12]]` is a wikilink, not a timestamp.

Every embedded image is checked: `![[…]]` with an image extension, every `![alt](…)` and every `<img src="…">`. Anything that isn't a Key frame of the bundle is an `unknown_frame`. `![[Some note]]` (no image extension) embeds a note and is ignored.

An **Unclear marker**, `[unclear]` or `[unclear: reason]`, marks a place where the Lecture itself is unreadable or inaudible. A line that is only a marker (`- [unclear: board out of focus]`) needs no Citation. A line that also states something still needs one: `- Python was invented in 1802 [unclear]` is a `missing_citation`. Timestamps on marker lines are checked as usual.

## Problems

| `problem` | When |
| --------- | ---- |
| `missing_citation` | An idea line has no Citation and is not just an Unclear marker |
| `timestamp_out_of_range` | A timestamp is after the end of the Lecture |
| `timestamp_not_near_content` | No Transcript segment or Key frame lies within 5 s of the timestamp |
| `link_time_mismatch` | A linked timestamp's `t=` differs from its label |
| `unknown_frame` | An embedded image is not a Key frame listed in the bundle's `manifest.json` |

The codes are stable. New codes may be added; existing ones won't change meaning.

## `--json` output

```json
{
  "ok": false,
  "problems": [
    {
      "line": 4,
      "problem": "missing_citation",
      "message": "idea has no Citation: - Loops are fast",
      "suggestion": "end the line with the timestamp it comes from, e.g. [12:34], or embed the Key frame it shows; mark unreadable parts [unclear]"
    }
  ]
}
```

- `ok`: `true` exactly when `problems` is empty (exit code 0)
- `problems`: in line order. A line can have several problems
- `line`: 1-based line number in the note
- `problem`: one of the codes above
- `message`, `suggestion`: human-readable text; don't parse it

When the exit code is 2, nothing is written to stdout; a one-line error goes to stderr.
