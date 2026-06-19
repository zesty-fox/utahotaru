from __future__ import annotations

import pytest

from strange_uta_game.backend.infrastructure.audio.base import AudioLoadError
from strange_uta_game.backend.infrastructure.audio.sounddevice_engine import (
    SoundDeviceEngine,
)


def test_position_stays_on_original_timeline(wav_file, fake_stream_factory):
    engine = SoundDeviceEngine(stream_factory=fake_stream_factory)
    try:
        engine.load(wav_file)
        engine.set_speed(0.5)
        engine.set_position_ms(500)
        assert engine.get_position_ms() == 500
    finally:
        engine.release()


def test_missing_file_raises_audio_load_error(fake_stream_factory):
    engine = SoundDeviceEngine(stream_factory=fake_stream_factory)
    with pytest.raises(AudioLoadError):
        engine.load("missing.wav")


def test_stop_resets_position(wav_file, fake_stream_factory):
    engine = SoundDeviceEngine(stream_factory=fake_stream_factory)
    try:
        engine.load(wav_file)
        engine.set_position_ms(500)
        engine.stop()
        assert engine.get_position_ms() == 0
    finally:
        engine.release()
