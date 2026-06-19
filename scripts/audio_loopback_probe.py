#!/usr/bin/env python3
"""Measure calibrated audio loopback latency and emit a schema-1 report."""

from __future__ import annotations

import argparse
import json
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path

import numpy as np


@dataclass(frozen=True)
class AcceptanceResult:
    errors_ms: tuple[float, ...]
    max_error_ms: float
    passed: bool


def detect_impulse_latency_ms(recorded: np.ndarray, sample_rate: int) -> float:
    """Return the strongest impulse position relative to recording start."""

    if sample_rate <= 0:
        raise ValueError("sample_rate must be positive")
    signal = np.asarray(recorded, dtype=np.float32)
    signal = np.max(np.abs(signal), axis=1) if signal.ndim > 1 else np.abs(signal)
    if not len(signal) or not np.any(signal):
        raise ValueError("no impulse detected")
    impulse_frame = int(np.argmax(signal))
    return impulse_frame / sample_rate * 1000.0


def evaluate_measurements(
    errors_ms: Sequence[float],
    threshold_ms: float = 10.0,
) -> AcceptanceResult:
    errors = tuple(float(value) for value in errors_ms)
    if not errors:
        raise ValueError("at least one measurement is required")
    maximum = max(abs(value) for value in errors)
    return AcceptanceResult(errors, maximum, maximum <= threshold_ms)


def _device_id(value: str) -> str | int:
    return int(value) if value.isdigit() else value


def record_measurements(
    input_device: str | int,
    output_device: str | int,
    *,
    runs: int,
    sample_rate: int,
    block_frames: int,
    calibration_ms: float,
) -> tuple[list[float], str]:
    """Play impulses through a physical loopback and return calibrated errors."""

    import sounddevice as sd

    pre_roll_frames = sample_rate // 20
    total_frames = sample_rate // 4
    output = np.zeros((total_frames, 1), dtype=np.float32)
    output[pre_roll_frames, 0] = 0.8
    errors: list[float] = []
    for _ in range(runs):
        recorded = sd.playrec(
            output,
            samplerate=sample_rate,
            channels=1,
            dtype="float32",
            device=(input_device, output_device),
            blocking=True,
            blocksize=block_frames,
        )
        detected_ms = detect_impulse_latency_ms(recorded, sample_rate)
        physical_latency_ms = detected_ms - pre_roll_frames / sample_rate * 1000.0
        errors.append(abs(physical_latency_ms - calibration_ms))

    output_info = sd.query_devices(output_device, "output")
    hostapi = sd.query_hostapis(output_info["hostapi"])
    return errors, str(hostapi["name"])


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--list-devices", action="store_true")
    parser.add_argument("--input")
    parser.add_argument("--output")
    parser.add_argument("--runs", type=int, default=20)
    parser.add_argument("--sample-rate", type=int, default=48000)
    parser.add_argument("--block-frames", type=int, default=1024)
    parser.add_argument("--calibration-ms", type=float, default=0.0)
    parser.add_argument("--report", type=Path, default=Path("audio-report.json"))
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    if args.list_devices:
        import sounddevice as sd

        print(sd.query_devices())
        return 0
    if args.input is None or args.output is None:
        raise SystemExit("--input and --output are required unless --list-devices is used")
    errors, backend = record_measurements(
        _device_id(args.input),
        _device_id(args.output),
        runs=args.runs,
        sample_rate=args.sample_rate,
        block_frames=args.block_frames,
        calibration_ms=args.calibration_ms,
    )
    result = evaluate_measurements(errors)
    report = {
        "schema": 1,
        "backend": backend,
        "sample_rate": args.sample_rate,
        "block_frames": args.block_frames,
        "errors_ms": list(result.errors_ms),
        "max_error_ms": result.max_error_ms,
        "passed": result.passed,
    }
    args.report.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False))
    return 0 if result.passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
