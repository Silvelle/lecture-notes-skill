"""Hardware probe and model choice, through `doctor` and `extract` with fake device reports."""

from __future__ import annotations

import io
from pathlib import Path

import pytest

from lecture_notes.cli import main
from lecture_notes.hardware import DeviceReport, Gpu
from tests.conftest import FakeTranscriber, read_json

CPU_ONLY = DeviceReport(gpus=(), cpu_count=8)
BIG_GPU = DeviceReport(
    gpus=(Gpu(name="RTX 4090", compute_capability=(8, 9), free_vram_mb=22000,
              compute_types=frozenset({"float16", "int8", "int8_float16", "float32"})),),
    cpu_count=16,
)
SMALL_GPU = DeviceReport(
    gpus=(Gpu(name="GTX 1650", compute_capability=(7, 5), free_vram_mb=3500,
              compute_types=frozenset({"float16", "int8", "float32"})),),
    cpu_count=8,
)
BLACKWELL = DeviceReport(
    gpus=(Gpu(name="RTX 5060 Ti", compute_capability=(12, 0), free_vram_mb=15000,
              compute_types=frozenset({"float16", "float32"})),),
    cpu_count=12,
)
GPU_UNKNOWN_VRAM = DeviceReport(
    gpus=(Gpu(name=None, compute_capability=None, free_vram_mb=None,
              compute_types=frozenset({"float16", "float32"})),),
    cpu_count=8,
)


@pytest.mark.parametrize(
    "report, tier, expected",
    [
        (CPU_ONLY, "cpu", "small on cpu (int8), 4 threads"),
        (BIG_GPU, "gpu_large", "large-v3 on cuda (float16)"),
        (SMALL_GPU, "gpu_small", "medium on cuda (float16)"),
        (BLACKWELL, "gpu_large", "large-v3 on cuda (float16)"),
        (GPU_UNKNOWN_VRAM, "gpu_unknown", "medium on cuda (float16)"),
    ],
    ids=["cpu-only", "big GPU", "small GPU", "Blackwell", "VRAM unknown"],
)
def test_doctor_shows_tier_and_chosen_defaults(
    report: DeviceReport, tier: str, expected: str, capsys: pytest.CaptureFixture[str]
) -> None:
    main(["doctor"], hardware=report)

    out = capsys.readouterr().out
    assert f"hardware tier:  {tier}" in out
    assert f"default model:  {expected}" in out


def test_extract_uses_the_chosen_model_and_records_it(
    lecture_file: Path, tmp_path: Path, fake_transcriber: FakeTranscriber
) -> None:
    bundle = tmp_path / "bundle"

    main(["extract", str(lecture_file), "-o", str(bundle)],
         transcriber_factory=fake_transcriber, hardware=BLACKWELL)

    assert fake_transcriber.choice is not None
    assert (fake_transcriber.choice.model, fake_transcriber.choice.compute_type) == ("large-v3", "float16")
    manifest = read_json(bundle / "manifest.json")
    assert (manifest["model"], manifest["device"]) == ("large-v3", "cuda")
    assert manifest["compute_type"] == "float16"
    assert manifest["hardware_tier"] == "gpu_large"


def test_model_and_device_options_override_the_choice(
    lecture_file: Path, tmp_path: Path, fake_transcriber: FakeTranscriber
) -> None:
    bundle = tmp_path / "bundle"

    main(["extract", str(lecture_file), "-o", str(bundle), "--model", "tiny", "--device", "cpu"],
         transcriber_factory=fake_transcriber, hardware=BIG_GPU)

    manifest = read_json(bundle / "manifest.json")
    assert (manifest["model"], manifest["device"], manifest["compute_type"]) == ("tiny", "cpu", "int8")


class Terminal(io.StringIO):
    def isatty(self) -> bool:
        return True


def long_lecture_cli(tmp_path: Path, lecture_file: Path, *extra: str) -> list[str]:
    # The fixture is 6 s; --assume-duration is not a user option, so stretch the estimate
    # with a model that is slow on CPU instead.
    return ["extract", str(lecture_file), "-o", str(tmp_path / "b"), "--model", "large-v3", *extra]


def test_long_cpu_job_asks_first_and_stops_on_no(
    lecture_file: Path, tmp_path: Path, fake_transcriber: FakeTranscriber,
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.setattr("lecture_notes.hardware.CONFIRM_ABOVE_SECONDS", 1.0)
    monkeypatch.setattr("sys.stdin", Terminal("n\n"))

    code = main(long_lecture_cli(tmp_path, lecture_file), transcriber_factory=fake_transcriber,
                hardware=CPU_ONLY)

    err = capsys.readouterr().err
    assert code == 1
    assert "Estimated" in err
    assert fake_transcriber.calls == []


def test_long_cpu_job_goes_ahead_on_yes(
    lecture_file: Path, tmp_path: Path, fake_transcriber: FakeTranscriber,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr("lecture_notes.hardware.CONFIRM_ABOVE_SECONDS", 1.0)
    monkeypatch.setattr("sys.stdin", Terminal("y\n"))

    code = main(long_lecture_cli(tmp_path, lecture_file), transcriber_factory=fake_transcriber,
                hardware=CPU_ONLY)

    assert code == 0 and fake_transcriber.calls


def test_long_cpu_job_without_a_terminal_needs_yes(
    lecture_file: Path, tmp_path: Path, fake_transcriber: FakeTranscriber,
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.setattr("lecture_notes.hardware.CONFIRM_ABOVE_SECONDS", 1.0)
    monkeypatch.setattr("sys.stdin", io.StringIO(""))

    code = main(long_lecture_cli(tmp_path, lecture_file), transcriber_factory=fake_transcriber,
                hardware=CPU_ONLY)
    assert code == 1
    assert "--yes" in capsys.readouterr().err

    code = main(long_lecture_cli(tmp_path, lecture_file, "--yes"),
                transcriber_factory=fake_transcriber, hardware=CPU_ONLY)
    assert code == 0 and fake_transcriber.calls


GPU_WITHOUT_CUDA_LIBRARIES = DeviceReport(
    gpus=(Gpu(name="RTX 5060 Ti", compute_capability=(12, 0), free_vram_mb=15000,
              compute_types=frozenset({"float16", "int8", "float32"}), cuda_libraries=False),),
    cpu_count=24,
)


def test_a_gpu_without_cuda_libraries_falls_back_to_cpu_with_a_hint(
    capsys: pytest.CaptureFixture[str],
) -> None:
    main(["doctor"], hardware=GPU_WITHOUT_CUDA_LIBRARIES)

    out = capsys.readouterr().out
    assert "hardware tier:  cpu" in out
    assert "default model:  small on cpu (int8), 8 threads" in out
    assert "nvidia-cublas-cu12" in out
