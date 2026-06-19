from __future__ import annotations

import pytest

from strange_uta_game.backend.infrastructure.audio.sounddevice_engine import (
    SoundDeviceEngine,
)


def test_diagnostics_report_requested_and_actual_latency(
    wav_file,
    fake_stream_factory,
):
    fake_stream_factory.latency = 0.023
    engine = SoundDeviceEngine(stream_factory=fake_stream_factory)
    try:
        engine.load(wav_file)

        diagnostics = engine.get_diagnostics()

        assert diagnostics.actual_latency_ms == pytest.approx(23.0)
        assert diagnostics.requested_latency_ms == pytest.approx(100.0)
        assert diagnostics.block_frames == 1024
        assert diagnostics.sample_rate == 32000
    finally:
        engine.release()
