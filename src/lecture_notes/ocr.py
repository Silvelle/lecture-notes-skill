"""Optional OCR of Key frames (the `ocr` extra plus the tesseract binary)."""

from __future__ import annotations

import shutil
import subprocess
from dataclasses import replace
from pathlib import Path

from lecture_notes.errors import warn
from lecture_notes.frames import KeyFrames

# Transcript language (ISO 639-1) to tesseract language pack.
TESSERACT_LANGUAGES = {
    "ru": "rus", "en": "eng", "uk": "ukr", "de": "deu", "fr": "fra", "es": "spa",
    "it": "ita", "pt": "por", "pl": "pol", "cs": "ces", "tr": "tur", "zh": "chi_sim",
    "ja": "jpn", "ko": "kor", "ar": "ara", "he": "heb", "hi": "hin", "kk": "kaz",
}


def available() -> bool:
    try:
        import pytesseract  # noqa: F401
    except ImportError:
        return False
    return shutil.which("tesseract") is not None


def installed_languages() -> list[str]:
    tesseract = shutil.which("tesseract")
    if tesseract is None:
        return []
    result = subprocess.run([tesseract, "--list-langs"], capture_output=True, text=True)
    lines = (result.stdout + result.stderr).splitlines()
    return [line.strip() for line in lines[1:] if line.strip() and " " not in line.strip()]


def add_text(key_frames: KeyFrames, bundle_dir: Path, language: str) -> KeyFrames:
    """Write `frame_<s>.txt` beside each Key frame: the Transcript language plus English.
    Unchanged when OCR isn't installed."""
    if key_frames.status != "extracted" or not available():
        return key_frames
    import pytesseract
    from PIL import Image

    installed = installed_languages()
    wanted = TESSERACT_LANGUAGES.get(language, language)
    languages = [wanted] if wanted in installed and wanted != "eng" else []
    if wanted != "eng" and wanted not in installed:
        warn(f"no tesseract pack for {language!r}; OCR uses English only "
             f"(install tesseract-ocr-{wanted})")
    languages.append("eng")
    frames = []
    for frame in key_frames.frames:
        image_path = bundle_dir / frame.file
        with Image.open(image_path) as image:
            text = pytesseract.image_to_string(image, lang="+".join(languages))
        text_file = Path(frame.file).with_suffix(".txt")
        (bundle_dir / text_file).write_text(text, encoding="utf-8")
        frames.append(replace(frame, ocr_text=str(text_file)))
    return replace(key_frames, frames=frames, ocr_languages=languages)
