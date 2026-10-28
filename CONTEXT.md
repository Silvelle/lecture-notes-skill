# Lecture Notes

Turns recorded lectures into faithful, timestamped text that a human or an agent can read and check.

## Language

### Input

**Lecture**:
One recorded talk or class: speech plus whatever is shown (slides, screen, board).
_Avoid_: Video, talk, class

**Source**:
Where a Lecture comes from: a URL any supported site serves, or a local video file.
_Avoid_: Input, link

### Extraction

**Lecture bundle**:
The folder produced from one Lecture: Transcript, Key frames and a Manifest. The only thing notes may be written from.
_Avoid_: Output, export, package

**Transcript**:
The Lecture's speech as timestamped segments, in the spoken language.
_Avoid_: Subtitles, captions, text

**Transcript origin**:
Where the Transcript came from: human-written subtitles, auto-generated subtitles, or local speech recognition.
_Avoid_: Caption type, source

**Key frame**:
A still image taken from the Lecture at a timestamp where the shown content changed.
_Avoid_: Screenshot, thumbnail, snapshot

**Board content**:
Anything shown rather than spoken: slides, code on screen, formulas, diagrams, handwriting.
_Avoid_: Visuals, slides

**Manifest**:
The bundle's record of what was extracted and how: Source, language, Transcript origin, model, hardware tier.
_Avoid_: Metadata, config

### Notes

**Lecture note**:
One Obsidian note per Lecture: the Lecture's ideas grouped by topic, each with a Citation.
_Avoid_: Summary, notes, digest

**Citation**:
A reference from a line in a Lecture note to a timestamp in the Transcript or to a Key frame.
_Avoid_: Link, reference, source

**Faithfulness check**:
The automated verification that every idea in a Lecture note has a Citation that matches the Lecture bundle.
_Avoid_: Audit, validation, fact-check

**Unclear marker**:
An explicit flag in a Lecture note where the Lecture itself is unreadable or inaudible, used instead of a guess.
_Avoid_: TODO, placeholder
