"""faster-whisper backend (the `whisper` extra)."""

from __future__ import annotations

import sys
import wave
from pathlib import Path
from typing import Any

from lecture_notes.errors import LectureNotesError
from lecture_notes.transcriber import Segment, Transcription

# Fixed for now; hardware-based model choice comes with the hardware probe.
DEFAULT_MODEL = "small"


class FasterWhisperTranscriber:
    def __init__(self, model: str = DEFAULT_MODEL, device: str = "auto") -> None:
        try:
            import ctranslate2
            from faster_whisper import WhisperModel
        except ImportError:
            raise LectureNotesError(
                "speech recognition needs faster-whisper; install it with: "
                "pip install 'lecture-notes[whisper]'"
            ) from None
        if device == "auto":
            device = "cuda" if ctranslate2.get_cuda_device_count() > 0 else "cpu"
        self._model_class = WhisperModel
        self._model_name = model
        self._load(device)

    def _load(self, device: str) -> None:
        self._device = device
        # "default" keeps the model's own precision where the device supports it.
        self._model = self._model_class(self._model_name, device=device, compute_type="default")

    def transcribe(self, audio: Path, language: str | None) -> Transcription:
        samples = _read_wav(audio)
        try:
            return self._transcribe(samples, language)
        except RuntimeError as error:
            # A CUDA device can be visible while its runtime libraries (cuBLAS, cuDNN)
            # are not installed; that only surfaces once inference starts.
            if self._device != "cuda" or not _is_missing_cuda_library(error):
                raise
            print(f"lecture-notes: warning: {error}; falling back to CPU", file=sys.stderr)
            self._load("cpu")
            return self._transcribe(samples, language)

    def _transcribe(self, samples: Any, language: str | None) -> Transcription:
        segments, info = self._model.transcribe(samples, language=language)
        return Transcription(
            language=info.language,
            segments=[Segment(start=s.start, end=s.end, text=s.text.strip()) for s in segments],
            model=f"faster-whisper/{self._model_name}",
            device=self._device,
        )


def _is_missing_cuda_library(error: RuntimeError) -> bool:
    message = str(error).lower()
    return "cannot be loaded" in message and any(lib in message for lib in ("cublas", "cudnn", "cuda"))


def _read_wav(path: Path) -> Any:
    """16 kHz mono s16le WAV → float32 samples.

    Decoding here instead of letting faster-whisper open the file keeps PyAV out of
    the path; faster-whisper 1.2.1 passes an argument newer PyAV releases reject.
    """
    import numpy as np

    with wave.open(str(path), "rb") as wav:
        frames = wav.readframes(wav.getnframes())
    return np.frombuffer(frames, dtype=np.int16).astype(np.float32) / 32768.0
