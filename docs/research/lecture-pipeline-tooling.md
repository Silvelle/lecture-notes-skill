# Lecture pipeline tooling: research notes

Researched 2026-10-28, against primary sources only (official docs, repos/source, PyPI JSON metadata, model cards). Version numbers and wheel availability come from the PyPI JSON API on that date (`https://pypi.org/pypi/<pkg>/json`). Anything I could not verify is marked **(unverified)** and listed again at the end.

## TL;DR: recommendations

1. **Captions first, ASR as fallback.** Use the `yt_dlp.YoutubeDL` Python API with `writesubtitles` + `writeautomaticsub` + `skip_download`. Record whether each track came from `subtitles` (manual) or `automatic_captions` (ASR) as provenance in the bundle. Treat auto-captions as a lower-trust source than our own ASR. Install `yt-dlp[default]` (this pulls in yt-dlp-ejs) plus **deno**, which yt-dlp now needs for full YouTube support.
2. **Default ASR: faster-whisper (MIT).** Every compiled dependency (ctranslate2 4.8.4, onnxruntime, av, tokenizers) has cp314 manylinux wheels. Use `large-v3` or `turbo` in **float16** on the RTX 5060 Ti. **Do not use int8 on Blackwell (sm_120)**: CTranslate2 disabled it. On CPU, use `small`/`base` with int8. Keep `word_timestamps=True` and `vad_filter=True`.
3. **Drop WhisperX for now.** It declares `requires-python >=3.10,<3.14` and pins `torch~=2.8.0`, so it cannot install on Python 3.14.
4. **Optional Russian-strength backend: `onnx-asr`** (MIT, numpy + onnxruntime only, Python 3.11–3.14). It runs GigaAM v3 (a Russian model, MIT) and Parakeet/Canary v3 (25 EU languages including Russian, CC-BY-4.0) without torch. It gives token timestamps, but long audio needs VAD.
5. **Hardware probe without torch.** Use `ctranslate2.get_cuda_device_count()` and `get_supported_compute_types("cuda")`, which ship with faster-whisper. For free VRAM, add an optional `nvidia-ml-py` (NVIDIA's NVML bindings; the separate `pynvml` package is deprecated). Fall back to CPU int8 `small` on any failure.
6. **Key frames.** Run ffmpeg `scdet` (or `select='gt(scene,X)'`), then perceptual-hash dedup with `imagehash`, plus a "coverage floor" frame every N seconds. For a camera filming a board, scene scores are unreliable. Use stability or time sampling instead (design judgement, see §4).
7. **Reading frames.** By default, let the host multimodal agent read the embedded key frames. Claude documents a 2576 px long-edge high-res tier on 4.7+ models. Make OCR optional: tesseract `rus+eng` is the lightest searchable-text layer. Avoid Nougat, which says Russian "will not work", and treat Surya weights as license-restricted.
8. **Skill format.** Write `SKILL.md` to the **agentskills.io spec** fields only (`name`, `description`, `license`, `compatibility`, `metadata`, `allowed-tools`) so it is portable. Codex, Gemini CLI and Cursor all document the same standard and the `.agents/skills/` location. Distribute through a Claude Code plugin marketplace (`.claude-plugin/marketplace.json`).
9. **Differentiation.** The closest prior art is `drpwchen/lecture-to-notes` (113 stars, explicit "traceability" goal, but Chinese-centric, GPU-oriented, and HTML-viewer-first). Gaps we can own:
   - a machine-checkable faithfulness contract (every note line carries a timestamp, and a verifier checks it against the bundle)
   - first-class non-English input (Russian lecture with English code on screen)
   - board/camera lectures, not just slides
   - CPU-safe defaults
   - Obsidian-native output
   - a portable agent skill plus a plain CLI

---

## 1. Subtitles via yt-dlp

### Flags and Python API

| CLI | `YoutubeDL` param | Meaning | Source |
|---|---|---|---|
| `--write-subs` | `writesubtitles` | Write subtitle file | [README](https://raw.githubusercontent.com/yt-dlp/yt-dlp/master/README.md), [YoutubeDL.py](https://raw.githubusercontent.com/yt-dlp/yt-dlp/master/yt_dlp/YoutubeDL.py) |
| `--write-auto-subs` | `writeautomaticsub` | Write automatically generated subtitles | same |
| `--list-subs` | `listsubtitles` | List available subtitles (simulates unless `--no-simulate`) | same |
| `--sub-format FMT` | `subtitlesformat` | Preference list, e.g. `ass/srt/best` | same |
| `--sub-langs LANGS` | `subtitleslangs` | List of languages; regex; `all`; `-` prefix excludes, e.g. `['all','-live_chat']` | same |
| `--skip-download` | `skip_download` | Don't download the media | same |
| `--convert-subs FMT` | (postprocessor) | Convert to ass, lrc, srt, vtt | [README](https://raw.githubusercontent.com/yt-dlp/yt-dlp/master/README.md) |
| `--cookies-from-browser` | `cookiesfrombrowser` | Tuple such as `('firefox', 'default', None, 'Meta')` | same |
| `--js-runtimes` | `js_runtimes` | e.g. `{'deno': {'path': ...}}`; deno is the default | same |

- Embedding: call `ydl.extract_info(url, download=False)` and then `ydl.sanitize_info(info)`. The return value of `extract_info` is not guaranteed to be JSON-serialisable. `devscripts/cli_to_api.py` maps CLI switches to API params. Don't parse stdout. ([README "Embedding yt-dlp"](https://raw.githubusercontent.com/yt-dlp/yt-dlp/master/README.md))
- **Info-dict fields** ([extractor/common.py docstring](https://raw.githubusercontent.com/yt-dlp/yt-dlp/master/yt_dlp/extractor/common.py)):
  - `subtitles` is `{tag: [subformat, ...]}`, sorted from lower to higher preference. Each subformat has `ext` plus either `data` or `url`, and optionally `name`, `http_headers` and `impersonate`.
  - `automatic_captions` is defined as "Like 'subtitles'; contains automatically generated captions".
  - This split is our manual-vs-auto provenance signal.
- **YouTube formats.** The YouTube extractor offers each track in `('json3', 'srv1', 'srv2', 'srv3', 'ttml', 'srt', 'vtt')`. It strips `xosf=1` because that "results in undesirable text position data for vtt, json3 & srv*" ([`_video.py` L142, L4214-4226](https://github.com/yt-dlp/yt-dlp/blob/master/yt_dlp/extractor/youtube/_video.py)).
  - Auto-translated tracks also appear in `automatic_captions`, using `tlang`. Skip them with `--extractor-args youtube:skip=translated_subs` ([README](https://raw.githubusercontent.com/yt-dlp/yt-dlp/master/README.md)).
  - The original-language auto track is keyed `<lang>-orig` (same source file, L4315-4335).
  - Whether json3/srv3 auto-captions carry per-word offsets is **(unverified)** from docs.
- **Fetching subs when the video is blocked.** On a playability failure (including "Sign in…"), the extractor calls `raise_no_formats(reason, expected=True)` ([`_video.py` ~L4070-4083](https://github.com/yt-dlp/yt-dlp/blob/master/yt_dlp/extractor/youtube/_video.py)). `--ignore-no-formats-error` (`ignore_no_formats_error`) is documented as "Useful for extracting metadata even if the videos are not actually available for download (experimental)" ([options.py](https://raw.githubusercontent.com/yt-dlp/yt-dlp/master/yt_dlp/options.py)).
  - Whether caption tracks are still present in that case is **(unverified)**: they come from the same player response that failed.
  - Separately, subtitle URLs themselves may need a **Subs PO token** on the `web` client (see below).

### Bot checks and mitigations (current state)

- **JS runtime is now required.** yt-dlp-ejs is "Required for full YouTube support", and needs a JS runtime: deno (recommended, enabled by default), node, bun or QuickJS ([README](https://raw.githubusercontent.com/yt-dlp/yt-dlp/master/README.md)). Minimum versions are Deno 2.3.0, Node 22, and Bun 1.2.11 (deprecated). `pip install -U "yt-dlp[default]"` includes yt-dlp-ejs ([EJS wiki](https://github.com/yt-dlp/yt-dlp/wiki/EJS)).
- **PO tokens.**
  - YouTube is gradually enforcing them. Currently only GVS and Subs require them, and only for some clients. Subs require one on the `web` client.
  - The recommended approach is a **PO Token Provider plugin** (bgutil-ytdlp-pot-provider, maintained by a yt-dlp maintainer). Manual extraction is "no longer recommended" because tokens are bound to video IDs.
  - Source: [PO Token Guide](https://github.com/yt-dlp/yt-dlp/wiki/PO-Token-Guide), last edited 2026-07-12. The extractor also prints a hint suggesting `youtube:po_token={client}.subs+XXX` ([`_video.py` L3213](https://github.com/yt-dlp/yt-dlp/blob/master/yt_dlp/extractor/youtube/_video.py)).
- **Cookies.**
  - The FAQ recommends `--cookies-from-browser`, or `--cookies FILE`. Exporting writes cookies "for ALL sites", so keep the file private ([FAQ](https://github.com/yt-dlp/yt-dlp/wiki/FAQ)).
  - For YouTube specifically, the Extractors wiki gives a private-window export procedure. It warns that you "run the risk of [the account] being banned (temporarily or permanently)" and suggests a throwaway account.
  - Rate limits: guests get about 300 videos/hour, accounts about 2000/hour. Recommended delay is 5–10 s (`-t sleep`) ([Extractors wiki](https://github.com/yt-dlp/yt-dlp/wiki/Extractors)).
- **The "Sign in to confirm you're not a bot" message.** The extractor detects any reason containing "sign in", strips YouTube's "This helps protect our community" suffix, and appends its own login hint ([`_video.py` ~L4071](https://github.com/yt-dlp/yt-dlp/blob/master/yt_dlp/extractor/youtube/_video.py)). The wiki and FAQ do not name this exact phrase, and I found no canonical maintainer issue for it **(unverified)**.
- **Implication for us.** Never ask for or handle the user's cookies ourselves. Document `--cookies-from-browser` as a user-side opt-in, add sleep between requests, and fall back to local files.

### License and versions

- yt-dlp is **Unlicense**. The repo, sdist and wheel contain only Unlicense code. PyInstaller-bundled executables are GPLv3+ ([README](https://raw.githubusercontent.com/yt-dlp/yt-dlp/master/README.md)).
- Requires Python 3.11+ ([README](https://raw.githubusercontent.com/yt-dlp/yt-dlp/master/README.md)). The latest is **2026.10.26** ([PyPI](https://pypi.org/project/yt-dlp/)); the author has 2026.10.21 installed.

## 2. Local speech-to-text

### Comparison

| Tool | License | Install footprint / Py 3.14 | GPU / CPU | Memory figures (own docs) | Word timestamps | VAD | Notes |
|---|---|---|---|---|---|---|---|
| **faster-whisper** 1.2.1 | MIT | Pure-py wheel. Deps `ctranslate2`, `onnxruntime`, `av`, `tokenizers` all have **cp314** wheels ([PyPI](https://pypi.org/project/faster-whisper/)). No system ffmpeg needed (PyAV) | CUDA 12 + cuDNN 9; CPU int8 | 13-min clip, large-v2 on a 3070 Ti: fp16 1m03s / 4525 MB; int8 59s / 2926 MB; batched(8) fp16 17s / 6090 MB. CPU small on an i7-12700K, 8 threads: int8 1m42s / 1477 MB RAM ([README](https://github.com/SYSTRAN/faster-whisper)) | `word_timestamps=True` | Silero, `vad_filter=True` | Model aliases include `large-v3`, `turbo`/`large-v3-turbo`, `distil-large-v3.5` ([utils.py](https://raw.githubusercontent.com/SYSTRAN/faster-whisper/master/faster_whisper/utils.py)) |
| **openai-whisper** 20250625 | MIT (code + weights) | sdist only; needs torch, numba, tiktoken (all cp314 on PyPI). README says "compatible with Python 3.8-3.11" ([README](https://github.com/openai/whisper)) | CUDA via torch / CPU | VRAM: tiny/base ~1 GB, small ~2 GB, medium ~5 GB, large ~10 GB, turbo ~6 GB ([README](https://github.com/openai/whisper)) | yes (README doesn't document it **(unverified here)**) | no | Reference implementation; slowest in faster-whisper's benchmark |
| **whisper.cpp** | MIT | C++; Python via community bindings | CUDA, Vulkan, OpenVINO, ROCm, CoreML, CPU AVX | Memory: tiny ~273 MB … medium ~2.1 GB, large ~3.9 GB; quantisation (e.g. Q5_0) ([README](https://github.com/ggml-org/whisper.cpp)) | experimental (`-ml 1`) | Silero (`--vad`) | Most portable for weak laptops |
| **pywhispercpp** 1.5.1 | MIT | **cp314** wheels, but "Basic Pre-built CPU wheels". CUDA needs `GGML_CUDA=1` source build ([README](https://github.com/absadiki/pywhispercpp)) | CPU (wheel) / CUDA (build) | as whisper.cpp | `token_timestamps`, `split_on_word` | not built in | |
| **WhisperX** 3.8.6 | BSD-2-Clause | **`requires-python >=3.10,<3.14`**; pins `torch~=2.8.0`, pyannote-audio ≥4 ([pyproject](https://raw.githubusercontent.com/m-bain/whisperX/main/pyproject.toml), [PyPI](https://pypi.org/project/whisperx/)) | CUDA 12.8 | "<8GB" for large-v2 beam 5; "70x realtime" ([README](https://github.com/m-bain/whisperX)) | wav2vec2 forced alignment. Russian model `jonatasgrosman/wav2vec2-large-xlsr-53-russian` ([alignment.py L79](https://raw.githubusercontent.com/m-bain/whisperX/main/whisperx/alignment.py)). Numerals can't be aligned | yes | Diarization needs an HF token and a gated model. **Not installable on Py 3.14** |
| **Parakeet TDT 0.6B v3** | CC-BY-4.0 | NeMo (`nemo_toolkit['asr']`, torch) or onnx-asr | NVIDIA (Ampere, Hopper, **Blackwell**, Volta listed) | ≥2 GB RAM; up to 24 min with full attention (A100), 3 h with local attention ([card](https://huggingface.co/nvidia/parakeet-tdt-0.6b-v3)) | word / segment / char | — | 25 languages incl. **ru**: FLEURS WER 5.51% (normalised, no punctuation) |
| **Canary 1B v2** | CC-BY-4.0 | NeMo | NVIDIA | — | word / segment (ASR) | — | 25 languages incl. ru; ASR + translation ([card](https://huggingface.co/nvidia/canary-1b-v2)) |
| **GigaAM v3** | MIT | torch; long-form needs pyannote + HF token ([README](https://github.com/salute-developers/GigaAM)) | CPU/GPU | — | `word_timestamps=True` (added 2026/04) | external (pyannote) | Russian-specific. `v3_e2e_*` models output punctuation/normalisation. `.transcribe` handles ≤25 s only |
| **onnx-asr** 0.12.0 | MIT | numpy + onnxruntime, **Python 3.11–3.14**, no torch/ffmpeg ([README](https://github.com/istupakov/onnx-asr)) | CPU; CUDA/TensorRT/ROCm/DirectML via ORT | RTFx ~36 (Parakeet, 9800X3D CPU), ~320 (RTX 5070 Ti, TensorRT) | token timestamps | yes (needed for >20–30 s) | Runs GigaAM v2/v3, Parakeet, Canary, Whisper, T-One |
| **distil-large-v3** | MIT | via faster-whisper | — | 6.3x faster than large-v3 | — | — | **English-only** ("Distil-Whisper English series") ([card](https://huggingface.co/distil-whisper/distil-large-v3)). Not usable for Russian |
| **large-v3-turbo** | MIT | via faster-whisper (`turbo`) | — | 809M params; decoder 32→4 layers; "minor quality degradation" ([card](https://huggingface.co/openai/whisper-large-v3-turbo)) | yes | — | Multilingual. "Not trained for translation" ([README](https://github.com/openai/whisper)) |

- **Multilingual and Russian quality.**
  - Whisper's README says performance "varies widely depending on the language", and gives a per-language WER figure for large-v3/v2 on Common Voice 15 and Fleurs ([README](https://github.com/openai/whisper)). I could not read the Russian number from the figure **(unverified)**.
  - GigaAM claims its e2e models beat Whisper 70:30 in LLM-judged side-by-side tests. That claim is from the project, not independent ([README](https://github.com/salute-developers/GigaAM)).
- **Mixed-language input.** For a Russian lecture with English code terms, Whisper's single `language=` per segment is a known risk. Our harness should test this. **(unverified, no primary source evaluates code-switching)**

### Blackwell (RTX 50, sm_120) status

- **PyTorch.**
  - 2.7 was the first release with Blackwell support, labelled prototype, with CUDA 12.8 wheels ([PyTorch 2.7 blog](https://pytorch.org/blog/pytorch-2-7/)).
  - The current PyPI `torch` 2.14.1 Linux wheel depends on `cuda-toolkit==13.0.3` and `nvidia-cudnn-cu13`, and ships cp314 wheels ([PyPI JSON](https://pypi.org/pypi/torch/json)).
  - The releases page says CUDA 13.0 is now the stable default ([releases](https://github.com/pytorch/pytorch/releases)).
- **CTranslate2.**
  - v4.6.1 added Python 3.14 support. v4.6.2 says "**Disable INT8 for sm120 - Blackwell GPUs**". v4.6.3 added "Support for CUDA 12.8" and made cuDNN optional (pure-CUDA Conv1d). v4.8.4 is dated 2026-10-24 ([CHANGELOG](https://raw.githubusercontent.com/OpenNMT/CTranslate2/master/CHANGELOG.md)).
  - No CUDA 13 entry is listed.
  - A faster-whisper user on an RTX 5070 Ti hit `CUBLAS_STATUS_NOT_SUPPORTED`. `--compute_type float16` worked ([issue #1260](https://github.com/SYSTRAN/faster-whisper/issues/1260)).
  - **So on the 5060 Ti, use `float16`.** Avoid `int8`, `int8_float16` and `auto` until verified on the actual card.
- The CTranslate2 install doc still says "cuDNN 8 for CUDA 12.x" ([installation.md](https://github.com/OpenNMT/CTranslate2/blob/master/docs/installation.md)). This contradicts the changelog (cuDNN 9 since 4.5.0), so the doc is stale.

## 3. Hardware detection and safe defaults

- **CTranslate2** (already a faster-whisper dependency):
  - `ctranslate2.get_cuda_device_count()` ([API index](https://opennmt.net/CTranslate2/python/ctranslate2.html)).
  - `ctranslate2.get_supported_compute_types(device: str, device_index: int = 0) -> set[str]` ([doc](https://opennmt.net/CTranslate2/python/ctranslate2.get_supported_compute_types.html)).
  - `CT2_VERBOSE=1` logs detected capabilities. Unsupported types are converted implicitly at load, e.g. int16→float16 on CC ≥8.0. int8 needs an NVIDIA GPU with CC ≥7.0 (or 6.1), an x86-64 CPU with MKL/oneDNN, or ARM64 with Ruy ([quantization doc](https://opennmt.net/CTranslate2/quantization.html)).
  - Whether `get_supported_compute_types("cuda")` already excludes int8 on sm_120 **(unverified)**. Check it on the target card.
- **Free VRAM:** `nvidia-ml-py` (author: NVIDIA, BSD, pure-Python `py3-none-any`, import name `pynvml`). `nvmlInit()` → `nvmlDeviceGetHandleByIndex(i)` → `nvmlDeviceGetMemoryInfo(h).free` ([PyPI](https://pypi.org/project/nvidia-ml-py/)). The PyPI package named `pynvml` is **deprecated** and depends on `nvidia-ml-py` ([PyPI](https://pypi.org/project/pynvml/)). NVML ships with the driver, so the import fails cleanly on machines without NVIDIA.
- **What faster-whisper documents for CPU.**
  - The usage shows `WhisperModel(model_size, device="cpu", compute_type="int8")`. Threads are set with `OMP_NUM_THREADS`.
  - Its CPU benchmark uses **`small`**: int8, 13 min audio in 1m42s, 1477 MB RAM, 8 threads on an i7-12700K ([README](https://github.com/SYSTRAN/faster-whisper)).
  - It publishes no CPU figures for medium/large, so recommending anything above `small` on weak CPUs is our own extrapolation.
- **Proposed policy** (design, not sourced):
  - No CUDA → CPU int8 `small` (`base` if RAM < 4 GB).
  - CUDA with free VRAM ≥ 6 GB → `large-v3` float16. The README shows 4525 MB at fp16 for large-v2 and 6090 MB batched.
  - CUDA with 3–6 GB → `turbo` float16 (unverified VRAM).
  - Any GPU error → retry on CPU.
  - Always let the user override.

## 4. Key-frame extraction

| Method | What it gives | Source |
|---|---|---|
| ffmpeg `select='gt(scene,X)'` | The `scene` value is 0–1. "Comparing scene against a value between 0.3 and 0.5 is generally a sane choice" | [ffmpeg-filters §select](https://ffmpeg.org/ffmpeg-filters.html#select_002c-aselect) |
| ffmpeg `scdet` | Sets `lavfi.scd.score` / `lavfi.scd.time` metadata. `threshold` is a % of max change; "Good values are in the [8.0, 14.0] range", default 10. `sc_pass=1` passes only scene-change frames | [ffmpeg-filters §scdet](https://ffmpeg.org/ffmpeg-filters.html#scdet-1) |
| ffmpeg `freezedetect` | Logs `freeze_start/duration/end` when content is static for `d` seconds (default 2 s, noise -60 dB). Useful to find "settled" moments: a slide fully built, or the board left alone | [ffmpeg-filters §freezedetect](https://ffmpeg.org/ffmpeg-filters.html#freezedetect) |
| ffmpeg `mpdecimate` | Drops near-duplicate frames (aimed at low-bitrate encoding) | [ffmpeg-filters §mpdecimate](https://ffmpeg.org/ffmpeg-filters.html#mpdecimate) |
| **PySceneDetect** 0.7.2 (BSD-3-Clause) | ContentDetector (HSV, default 27), AdaptiveDetector (rolling average, for camera motion), ThresholdDetector (fades), HistogramDetector, HashDetector (perceptual hash, 0.395). `min_scene_len` 15 frames. OpenCV-based | [detectors docs](https://www.scenedetect.com/docs/latest/api/detectors.html), [repo](https://github.com/Breakthrough/PySceneDetect) |
| **imagehash** 4.3.2 (BSD-2-Clause) | aHash, pHash, dHash, wHash, colorhash, crop-resistant. `h1 - h2` = Hamming distance. Deps: Pillow, numpy, scipy | [README](https://github.com/JohannesBuchner/imagehash) |

- `opencv-python-headless` 5.0 ships `cp37-abi3` wheels, so it works on 3.14 ([PyPI](https://pypi.org/project/opencv-python-headless/)). `scenedetect` is pure-Python.
- **Slides and screen shares vs camera on a board** (design judgement):
  - *Slides/screen:* the content changes abruptly and the background is static. `scdet`/`select` scene scores plus a pHash dedup (to drop builds, cursor moves and re-shows) work well. Add a coverage floor so a 10-minute slide still gets frames. `claude-watch` does this every 45 s ([README](https://github.com/devinilabs/claude-watch)).
  - *Camera filming a board:* the lecturer's motion dominates the scene score, while the board changes slowly and additively. Scene detection either fires constantly or not at all. Better approaches:
    - fixed-interval sampling (e.g. every 20–30 s)
    - `freezedetect`-style "settled" frames
    - hash/diff computed on a downscaled frame
    - keeping the *last* frame before an erase, which holds the most content
  - lecture2notes trained a classifier distinguishing `slide`, `presenter_slide`, `whiteboard`, `presenter_whiteboard`, etc., but only uses slide classes downstream ([docs](https://lecture2notes.readthedocs.io/en/latest/models/slide-classifier.html)). That is evidence the board case is unsolved in prior art.
- No primary source benchmarks these methods on board lectures **(unverified)**. Plan an eval on real samples.

## 5. Reading frames (OCR / vision)

| Tool | License | Cyrillic / Russian | Maturity / notes |
|---|---|---|---|
| **Tesseract** (+ pytesseract 0.3.13, Apache-2.0) | Apache-2.0 (engine) **(tessdata license unverified)** | `rus` in all versions; `cyrl` script model in 4.0.0 tessdata/best/fast ([tessdoc](https://tesseract-ocr.github.io/tessdoc/Data-Files-in-different-versions.html)) | System package. Lightest option. ffmpeg also has an `ocr` filter |
| **EasyOCR** 1.7.2 | Apache-2.0 | 80+ languages incl. Cyrillic; "English is compatible with every language" ([README](https://github.com/JaidedAI/EasyOCR)) | PyTorch. Last release Sept 2024; issues auto-closed after 6 months |
| **PaddleOCR** 3.7.0 | Apache-2.0 | PP-OCRv5 multilingual covers 109 languages incl. Cyrillic ([README](https://github.com/PaddlePaddle/PaddleOCR)) | Needs `paddlepaddle`, which has **no cp314 wheels** (latest 3.3.1 tops out at cp313, [PyPI](https://pypi.org/project/paddlepaddle/)) |
| **RapidOCR** 3.10.0 | Apache-2.0 (code; models from PaddleOCR) | Default zh/en; others via its model list ([README](https://github.com/RapidAI/RapidOCR)) **(Russian model availability unverified)** | ONNX Runtime / OpenVINO etc. No paddle needed |
| **docTR** 1.1.0 | Apache-2.0 | `VOCABS["russian"]` exists ([vocabs.py](https://github.com/mindee/doctr/blob/main/doctr/datasets/vocabs.py)); a pretrained Russian recogniser is **(unverified)** | PyTorch; Python ≥3.11 |
| **Surya** 0.22.1 | Code Apache-2.0; **weights modified OpenRAIL-M**, free for research, personal use and orgs <$5M ([README](https://github.com/datalab-to/surya)) | 90+ languages; `ru` 88.8% on their benchmark | Also does math → KaTeX-LaTeX in `<math>` tags. GPU path via vLLM/Docker |
| **pix2tex / LaTeX-OCR** 0.1.4 | MIT | n/a (math) | Equation image → LaTeX. Handwriting "kinda done" ([README](https://github.com/lukas-blecher/LaTeX-OCR)) |
| **texify** | Code GPL-3.0, weights CC BY-SA 4.0 | English-focused | **Deprecated**, moved into Surya ([README](https://github.com/VikParuchuri/texify)) |
| **Nougat** | Code MIT, **weights CC-BY-NC** | README: Russian documents "will not work" | Built for full PDF pages of papers, not video frames ([README](https://github.com/facebookresearch/nougat)) |
| **DECIMER** 2.8.1 | MIT | n/a (chemistry) | Structure image → SMILES; TensorFlow; has a hand-drawn model ([README](https://github.com/Kohulan/DECIMER-Image_Transformer)) |
| **MolScribe** 1.1.1 | MIT | n/a (chemistry) | Image → molecular graph/SMILES, PyTorch. PyPI last upload 2023 ([README](https://github.com/thomas0809/MolScribe), [PyPI](https://pypi.org/project/molscribe/)) |

**Alternative: the host agent reads the frames** ([Claude vision docs](https://platform.claude.com/docs/en/build-with-claude/vision)):

- **Limits.** Images up to 8000×8000 px. JPEG/PNG/GIF/WebP. Up to 100 images per API request for 200k-context models, 600 for others, 20 per message on claude.ai.
- **Many-image requests.** Above 20 images in one request, a stricter per-image limit applies. Keeping each image ≤2000 px avoids it.
- **Resolution tiers.** Claude 4.7+ uses a high-res tier (2576 px long edge, 4784 visual tokens). Older models are capped at 1568 px. Cost is `⌈w/28⌉×⌈h/28⌉` tokens.
- **Documented limitations:** may "hallucinate or make mistakes when interpreting low-quality, rotated, or very small images". Text should be legible.
- **Implication.** Store frames at ≤1920 px (or ≤2000 px when there are many). Embed them in the bundle. Have the agent transcribe on-screen code/formulas itself, marked as *read from frame @ t*. Treat OCR as optional, as a search index or cross-check rather than the source of truth.
- **Other agents.** Whether Codex, Gemini CLI or Cursor can read local image files is not covered here **(unverified)**.

## 6. Obsidian format facts

- **Internal links.** Default is a wikilink `[[Note]]`. The Markdown alternative is `[Note](Note%20name.md)`, toggled by Settings → Files and Links → "Use [[Wikilinks]]".
  - Heading link: `[[Note#Heading]]`. Block link: `[[Note#^id]]`; IDs use Latin letters, numbers and dashes only. Display text: `[[Note|text]]`.
  - Characters `# | ^ : %% [[ ]]` can break links, so avoid them in file names ([Internal links](https://obsidian.md/help/links)).
- **Embeds.**
  - Images: `![[img.png]]`, resized with `![[img.png|100]]` or `|100x145`.
  - Notes, headings and blocks: `![[Note#heading]]` and `![[Note#^id]]`.
  - PDFs: `![[Doc.pdf#page=3]]` ([Embed files](https://obsidian.md/help/embeds)).
  - External images: `![alt](url|640x480)` style sizing ([Basic syntax](https://obsidian.md/help/syntax)).
  - Inside tables, escape `|` with a backslash ([Advanced syntax](https://obsidian.md/help/advanced-syntax)).
- **Properties (frontmatter).**
  - YAML at the top of the file. Types: Text, List, Number, Checkbox, Date, Date & time, Tags. Defaults: `tags`, `aliases`, `cssclasses`.
  - Links in properties must be quoted (`"[[Link]]"`). **Nested properties are not supported** in the UI. JSON frontmatter is read and saved back as YAML ([Properties](https://obsidian.md/help/properties)).
- **Math.** LaTeX rendered with **MathJax**: `$…$` inline, `$$…$$` block ([Advanced syntax](https://obsidian.md/help/advanced-syntax)).
- **Mermaid.**
  - Use a fenced `mermaid` block. Link nodes to notes with `class A,B internal-link;`. Quote names that contain special characters.
  - These links don't appear in Graph view ([Advanced syntax](https://obsidian.md/help/advanced-syntax)).
- **Callouts.**
  - Syntax is `> [!type] Title`. `+`/`-` makes them foldable.
  - Types: note, abstract (summary, tldr), info, todo, tip (hint, important), success (check, done), question (help, faq), warning (caution, attention), failure (fail, missing), danger (error), bug, example, quote (cite).
  - Unknown types render as `note` ([Callouts](https://obsidian.md/help/callouts)).
- **Other syntax.**
  - Comments `%%…%%` are visible only in editing view. Footnotes `[^1]`. Highlights `==text==` ([Basic syntax](https://obsidian.md/help/syntax)).
  - Comments are a candidate for hidden provenance markers, but they are visible when editing. `<!-- -->` hides text in other apps too.
- **External timestamps.**
  - Obsidian treats any URL as an external link ([syntax](https://obsidian.md/help/syntax)).
  - YouTube Help documents only the Share → "Start at" UI ([YouTube Help](https://support.google.com/youtube/answer/57741)). The `?t=<seconds>` / `&t=` URL parameter itself is not documented there **(unverified as an official contract; widely observed behaviour)**.
  - For local files there is no portable timestamp link in core Obsidian **(unverified; plugins such as Media Extended exist)**.

## 7. Agent skills format

- **Open spec** ([agentskills.io/specification](https://agentskills.io/specification)).
  - A skill is a directory with `SKILL.md`, plus optional `scripts/`, `references/` and `assets/`.
  - Frontmatter:
    - `name` (required): 1–64 chars, `a-z0-9-`, no leading/trailing/consecutive hyphens, **must match the directory name**.
    - `description` (required): 1–1024 chars; say what the skill does *and* when to use it.
    - Optional: `license`, `compatibility` (≤500 chars, e.g. "Requires Python 3.14+ and uv"), `metadata` (string→string map), and `allowed-tools` (experimental).
  - Size: metadata ~100 tokens; body "< 5000 tokens recommended"; "Keep your main `SKILL.md` under 500 lines".
  - Reference files with relative paths from the skill root, kept one level deep. Validate with `skills-ref validate`.
  - The format was "originally developed by Anthropic, released as an open standard" ([agentskills.io](https://agentskills.io/home)).
- **Anthropic docs** ([Agent Skills overview](https://platform.claude.com/docs/en/agents-and-tools/agent-skills/overview)).
  - Same three-level progressive disclosure. `name` cannot contain "anthropic" or "claude".
  - Scripts run via bash and "only their output enters context".
  - Runtime differs by surface: the **Claude API has no network and no runtime package installs**, while Claude Code has full network access. An API-uploaded version of this skill therefore can't run yt-dlp or ASR.
- **Claude Code** ([Skills](https://code.claude.com/docs/en/skills)).
  - Extra fields: `disable-model-invocation`, `user-invocable`, `argument-hint`, `model`, `context: fork`, `agent`, `hooks`, `when_to_use`, `paths`, and others.
  - "Outside Claude Code, only the Agent Skills spec fields … are accepted. Any other key causes a hard error on upload or packaging."
  - `${CLAUDE_SKILL_DIR}` references bundled scripts, e.g. `allowed-tools: Bash(${CLAUDE_SKILL_DIR}/scripts/x.sh *)`.
  - Locations: `~/.claude/skills/`, `.claude/skills/`, or plugin `skills/<name>/SKILL.md`, invoked as `/plugin:skill`.
  - `description` + `when_to_use` is truncated at 1,536 chars in the listing.
- **Distribution** ([Plugin marketplaces](https://code.claude.com/docs/en/plugin-marketplaces)).
  - Put `.claude-plugin/marketplace.json` in the repo. It needs `name`, `owner`, and `plugins[]` entries with `name` and `source`. A source can be a relative path, `github`, `git-subdir`, `url`, `archive`, `npm` or `command`.
  - Users run `claude plugin marketplace add owner/repo`, then `claude plugin install <plugin>@<marketplace>`. Check with `claude plugin validate`.
  - Keep the entry name equal to the `plugin.json` name.
- **Other agents**:
  - **OpenAI Codex:** "build on the open agent skills standard". Locations: `.agents/skills` (repo, up to root), `$HOME/.agents/skills`, `/etc/codex/skills`. Optional `agents/openai.yaml` for invocation policy ([Codex skills docs](https://learn.chatgpt.com/docs/build-skills)).
  - **Gemini CLI:** "Based on the Agent Skills open standard". Locations: `~/.gemini/skills/` or `~/.agents/skills/`, and workspace `.gemini/skills/` or `.agents/skills/`, with `.agents` winning. The page notes that Gemini CLI was replaced by Antigravity CLI for unpaid/Google One users on 2026-06-18 ([Gemini CLI skills](https://geminicli.com/docs/cli/skills/)).
  - **Cursor:** `.agents/skills/` and `.cursor/skills/`. It also loads `.claude/skills/` and `.codex/skills/` (user and project). Extra fields: `paths`, `disable-model-invocation`, `icon`, `color` ([Cursor skills](https://cursor.com/docs/context/skills)).
  - **Portable layout:** spec-only frontmatter, scripts invoked by relative path, and the skill dir mirrored or symlinked into `.agents/skills/`. `${CLAUDE_SKILL_DIR}` is Claude-Code-only, so keep a fallback instruction ("run `scripts/x` relative to this file").

## 8. Prior art

Stars and licenses are from the GitHub API on 2026-10-28. Descriptions are from each README.

| Repo | ★ | License | What it does | Board / slide content | Faithfulness / timestamps |
|---|---|---|---|---|---|
| [drpwchen/lecture-to-notes](https://github.com/drpwchen/lecture-to-notes) | 113 | MIT | Local GPU pipeline: faster-whisper, slide extraction with pHash dedup, quick OCR → Surya OCR, local VLM, `ground_slides.py` aligns slides ↔ transcript, LLM synthesis. Synced HTML viewer and Obsidian-style vault export. Claude Code skill + CLI | Slides (video, PDF deck, photos). No explicit board handling | **Strongest:** the stated goal is "traceability: every claim … attachable to a moment in the transcript and to the slide". Has `audit_note.py`. Requires an explicit `--lang`; templates/config are Traditional-Chinese/Mandarin oriented |
| [JimmySadek/video-fetcher-to-markdown](https://github.com/JimmySadek/video-fetcher-to-markdown) | 512 | MIT | Portable skill (`npx skills add`): captions or local Whisper → archival Markdown with provenance (language, caption type, translated flag) | Contact-sheet frames for short videos only | Strong caption-provenance metadata; no note-level citation check |
| [devinilabs/claude-watch](https://github.com/devinilabs/claude-watch) | 124 | MIT | Claude Code plugin / claude.ai / Codex skill. ffmpeg scene detection plus 45 s coverage floor; captions or Whisper **API** (Groq/OpenAI); Claude reads every frame; templated `notes.md` | Slides/code via Claude vision ("Code & Commands" section) | Timestamps in notes; no verification |
| [KIRVO-REPORTING/video-to-notes](https://github.com/KIRVO-REPORTING/video-to-notes) | 109 | MIT | CLI + Codex skill: subtitles first, local Whisper fallback, "grounded AI summaries", HTML dashboard, Notion/Obsidian publishing (Chinese-first docs) | No | Claims grounded summaries; mechanism not inspected |
| [HHousen/lecture2notes](https://github.com/HHousen/lecture2notes) | 67 | AGPL-3.0 | Research code: slide classifier (9 classes incl. whiteboard), perspective crop, clustering, OCR, ASR, extractive/abstractive summarisation | Classifies whiteboards but uses only slide classes | Summaries; no timestamp guarantee |
| [LjyYano/skill-pack](https://github.com/LjyYano/skill-pack) | 43 | Apache-2.0 | Skill collection incl. video-to-note (Claude Code/Codex/OpenCode) | not inspected | not inspected |
| [aawhb/ytkn](https://github.com/aawhb/ytkn) | 11 | GPL-3.0 | Obsidian plugin: YouTube → AI knowledge notes | No | No |
| [csbune/youtube-capture-skill](https://github.com/csbune/youtube-capture-skill) | 0 | none | Claude Code skill → Obsidian note; **two scripts check the note against the transcript** ("fake quotes, wrong timestamps, and skipped sections all fail the check") | No | **Yes, verifier**, but transcript-only, Thai-specific, no license |
| [Paldom/video-to-skill](https://github.com/Paldom/video-to-skill) | 1 | MIT | Three agent skills: transcript (creator captions → orig-language auto → local Whisper, with a "deterministic quality verdict"), scene-change keyframes + tesseract OCR timeline, linked notes | Slides via scene change + OCR | Clickable timestamps |
| [yshestakov/lecture-processing](https://github.com/yshestakov/lecture-processing) | 2 | MIT | faster-whisper + scenedetect + imagehash → Markdown; `check_links.py` validates Obsidian links | Slides | Link checking only |
| [SuVirachet/youtube-to-obsidian](https://github.com/SuVirachet/youtube-to-obsidian) | 1 | MIT | Claude Code skill: timestamped transcript + concept note + HD screenshots | Screenshots | Timestamped transcript |
| [jieyu166/lecture2notes](https://github.com/jieyu166/lecture2notes) | 1 | MIT | Local ASR (several engines), slide capture, OCR, synced viewer; Claude Code/Codex skill | Slides | Viewer sync |
| [mohsinkhadim59/youtube-obsidian-mcp](https://github.com/mohsinkhadim59/youtube-obsidian-mcp) | 3 | MIT | MCP server: subtitles + screenshots → Obsidian | Screenshots | No |

**Gaps this project can own:**

1. **A faithfulness contract that can be checked by machine, across text and frames.**
   - Every note bullet cites `[mm:ss]` and is checked against the bundle: quotes must exist and timestamps must fall within segment bounds.
   - Frame-derived claims cite a frame ID.
   - Only csbune (transcript-only) and drpwchen (`audit_note.py`) do anything similar.
2. **Non-English first.** A Russian lecture with English code on screen means per-segment language handling, Cyrillic + Latin OCR or vision, and never silently machine-translating. Recorded provenance should distinguish manual subs, auto subs and our ASR.
3. **Board/camera lectures.** Nobody handles chalkboard/whiteboard capture beyond lecture2notes' unused classifier classes.
4. **Weak-laptop safety.** Hardware probe, CPU int8 `small` default, no mandatory torch, Python 3.14 compatible. Most competitors assume a GPU or a cloud Whisper API.
5. **Obsidian-native and portable.**
   - Obsidian side: properties typed for Obsidian (no nested keys), `![[frame.png|w]]` embeds, timestamp URLs, MathJax-ready LaTeX.
   - Portability side: one spec-only `SKILL.md` that works in Claude Code, Codex, Gemini CLI and Cursor, with a plain CLI producing the same bundle.
6. **Subject-agnostic visual reading.** Code, math, chemical structures and diagrams are read by the host agent from embedded frames, with optional specialist tools (pix2tex, DECIMER) as plug-ins rather than core dependencies.

---

## Unverified / open questions

- Whether YouTube caption tracks are still returned in `automatic_captions`/`subtitles` when playability fails ("Sign in…") with `--ignore-no-formats-error`. Test empirically.
- Whether json3/srv3 auto-captions contain per-word timing offsets. Not documented by yt-dlp; inspect real files.
- No canonical yt-dlp maintainer statement found specifically for "Sign in to confirm you're not a bot". Only the extractor's handling code and wiki pages on cookies, PO tokens and rate limits.
- `?t=` YouTube URL parameter: not in official YouTube Help (only the Share → Start at UI).
- Whisper large-v3 Russian WER: it is in the README's figure, which I could not read as text.
- Whether `ctranslate2.get_supported_compute_types("cuda")` reports int8 on sm_120 after the v4.6.2 change, and whether CTranslate2 4.8.x wheels (CUDA 12.x) run cleanly next to torch's CUDA 13 wheels in one venv. Test on the RTX 5060 Ti.
- VRAM for `turbo` / `large-v3` under faster-whisper fp16: only large-v2 figures are published.
- openai-whisper on Python 3.14: its own README says 3.8–3.11. The dependencies have cp314 wheels, but this is untested.
- docTR pretrained Russian recognition model availability. RapidOCR Russian model availability. Tesseract `tessdata` license.
- Board-lecture key-frame methods: no primary-source benchmark; needs our own evaluation set.
- Stars and README claims for prior art are self-reported. I did not run any of these tools.
- Whether Codex, Gemini CLI and Cursor agents can read local images referenced by a skill (needed if the agent reads key frames there).
