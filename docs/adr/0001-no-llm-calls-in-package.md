# The package never calls an LLM; the host agent writes the notes

The Python package only does deterministic extraction: it turns a Source into a Lecture bundle (Transcript, Key frames, Manifest) and runs the Faithfulness check. Writing the Lecture note is done by the host agent (Claude Code, Codex, Gemini CLI, Cursor) following the skill, reading the bundle including the Key frame images. We chose this over a standalone CLI that calls an LLM API because it needs no API key or per-use cost, works with any agent that supports `SKILL.md`, and keeps faithfulness checkable: the agent can only use what is in the bundle, and `verify` checks the note against it.

## Considered Options

- **Standalone CLI with an LLM API key.** Rejected: requires a key and money, ties the project to one provider, and the AI step becomes hidden inside the tool.
- **Both (built-in LLM mode as well as the skill).** Rejected for now: two note-writing paths to maintain and keep faithful. Can be reopened later as an optional extra without changing the bundle format.

## Consequences

- Without an agent, users still get a full readable Transcript and Key frames, but no Lecture note.
- **Not a contradiction:** the package *does* use local speech-recognition models (faster-whisper, onnx-asr) and optional OCR. These turn audio or images into text. They don't write, summarise or interpret anything. "No LLM" means the package never generates notes or other prose.
- The Lecture bundle format is the contract between the two halves, so changing it is a breaking change for the skill.
