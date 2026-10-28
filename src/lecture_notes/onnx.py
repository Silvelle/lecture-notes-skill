"""onnx-asr backend (the `ru` extra): GigaAM v3 for Russian, with Silero VAD for timestamps."""

from __future__ import annotations

from pathlib import Path

from lecture_notes.errors import LectureNotesError
from lecture_notes.hardware import TranscriberChoice
from lecture_notes.transcriber import Segment, Transcription


class OnnxAsrTranscriber:
    def __init__(self, choice: TranscriberChoice) -> None:
        try:
            import onnx_asr
        except ImportError:
            raise LectureNotesError(
                "the onnx-asr backend is not installed; pip install 'lecture-notes[ru]'"
            ) from None
        providers = (["CUDAExecutionProvider", "CPUExecutionProvider"]
                     if choice.device == "cuda" else ["CPUExecutionProvider"])
        self._choice = choice
        # GigaAM takes ~25 s at a time; voice activity detection cuts the Lecture into
        # speech segments, which also gives each one its timestamps. A low threshold and
        # some padding: dropping speech is worse than keeping a little noise.
        self._model = onnx_asr.load_model(choice.model, providers=providers).with_vad(
            onnx_asr.load_vad("silero", providers=providers),
            threshold=0.3, neg_threshold=0.15, speech_pad_ms=200,
        )

    def transcribe(self, audio: Path, language: str | None) -> Transcription:
        segments = [
            Segment(start=round(r.start, 3), end=round(r.end, 3), text=r.text.strip())
            for r in self._model.recognize(str(audio))
            if r.text.strip()
        ]
        return Transcription(language=language or "ru", segments=segments,
                             model=self._choice.model, device=self._choice.device)
