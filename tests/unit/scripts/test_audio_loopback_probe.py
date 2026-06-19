import json

import numpy as np
import pytest

from scripts import audio_loopback_probe
from scripts.audio_loopback_probe import (
    detect_impulse_latency_ms,
    evaluate_measurements,
)


def test_detect_impulse_latency_ms():
    recorded = np.zeros(4800, dtype=np.float32)
    recorded[480] = 1.0

    assert detect_impulse_latency_ms(recorded, sample_rate=48000) == pytest.approx(10.0)


def test_acceptance_rejects_error_over_ten_ms():
    result = evaluate_measurements([8.0, 9.5, 10.1])

    assert not result.passed
    assert result.max_error_ms == 10.1


def test_cli_writes_schema_one_report(tmp_path, monkeypatch):
    report_path = tmp_path / "audio-report.json"
    monkeypatch.setattr(
        audio_loopback_probe,
        "record_measurements",
        lambda *args, **kwargs: ([8.0, 9.5], "Core Audio"),
    )

    exit_code = audio_loopback_probe.main(
        ["--input", "1", "--output", "2", "--report", str(report_path)]
    )

    report = json.loads(report_path.read_text(encoding="utf-8"))
    assert exit_code == 0
    assert report["schema"] == 1
    assert report["backend"] == "Core Audio"
    assert report["passed"] is True
