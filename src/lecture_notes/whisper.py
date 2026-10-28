"""faster-whisper backend (the `whisper` extra)."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from lecture_notes import media
from lecture_notes.errors import LectureNotesError, warn
from lecture_notes.hardware import BACKENDS, FASTER_WHISPER, TranscriberChoice
from lecture_notes.transcriber import Segment, Transcription


class FasterWhisperTranscriber:
    def __init__(self, choice: TranscriberChoice) -> None:
        try:
            from faster_whisper import WhisperModel
        except ImportError:
            raise LectureNotesError(BACKENDS[FASTER_WHISPER].install_hint(FASTER_WHISPER)) from None
        self._model_class = WhisperModel
        self._choice = choice
        self._load(choice.device, choice.compute_type)

    def _load(self, device: str, compute_type: str) -> None:
        self._device = device
        self._compute_type = compute_type
        self._model = self._model_class(
            self._choice.model, device=device, compute_type=compute_type,
            cpu_threads=self._choice.cpu_threads, num_workers=1,
        )

    def transcribe(self, audio: Path, language: str | None) -> Transcription:
        samples = media.read_wav(audio)
        try:
            return self._transcribe(samples, language)
        except RuntimeError as error:
            # A CUDA device can be visible while its runtime libraries (cuBLAS, cuDNN)
            # are not installed; that only surfaces once inference starts.
            if self._device != "cuda" or not _is_missing_cuda_library(error):
                raise
            warn(f"{error}; falling back to CPU")
            self._load("cpu", "int8")
            return self._transcribe(samples, language)

    def _transcribe(self, samples: Any, language: str | None) -> Transcription:
        segments, info = self._model.transcribe(samples, language=language)
        return Transcription(
            language=info.language,
            segments=[Segment(start=s.start, end=s.end, text=s.text.strip()) for s in segments],
            model=self._choice.model,
            device=self._device,
            compute_type=self._compute_type,
        )


def _is_missing_cuda_library(error: RuntimeError) -> bool:
    message = str(error).lower()
    return "cannot be loaded" in message and any(lib in message for lib in ("cublas", "cudnn", "cuda"))
