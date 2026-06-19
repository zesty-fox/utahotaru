from __future__ import annotations

import numpy as np
import pytest
import soundfile as sf

from tests.unit.infrastructure.audio_fakes import FakeStreamFactory


@pytest.fixture
def wav_file(tmp_path, monkeypatch):
    sample_rate = 32000
    timeline = np.arange(sample_rate, dtype=np.float32) / sample_rate
    samples = np.sin(2 * np.pi * 440 * timeline).astype(np.float32) * 0.2
    path = tmp_path / "tone.wav"
    sf.write(path, samples, sample_rate)
    monkeypatch.setenv("SUG_CACHE_DIR", str(tmp_path / "cache"))
    return str(path)


@pytest.fixture
def fake_stream_factory():
    return FakeStreamFactory()
