from __future__ import annotations

import pytest

from strange_uta_game.backend.infrastructure.audio.base import AudioPlaybackError
from strange_uta_game.backend.infrastructure.audio.factory import (
    AudioBackend,
    create_audio_engine,
)
from strange_uta_game.backend.infrastructure.audio.sounddevice_engine import (
    SoundDeviceEngine,
)


def test_factory_uses_sounddevice_for_shared_backend():
    engine = create_audio_engine(AudioBackend.SHARED)

    assert isinstance(engine, SoundDeviceEngine)


def test_bass_preview_requires_explicit_opt_in(monkeypatch):
    monkeypatch.delenv("SUG_ENABLE_BASS_FALLBACK", raising=False)

    with pytest.raises(AudioPlaybackError, match="disabled"):
        create_audio_engine(AudioBackend.BASS_PREVIEW)
