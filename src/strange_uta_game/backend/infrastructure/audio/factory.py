"""Explicit construction boundary for audio backends."""

from __future__ import annotations

import os
from enum import StrEnum

from .base import AudioPlaybackError, IAudioEngine
from .profile import AudioProfile
from .sounddevice_engine import SoundDeviceEngine


class AudioBackend(StrEnum):
    SHARED = "shared"
    BASS_PREVIEW = "bass_preview"


def create_audio_engine(
    backend: AudioBackend = AudioBackend.SHARED,
    profile: AudioProfile | None = None,
) -> IAudioEngine:
    if backend is AudioBackend.SHARED:
        return SoundDeviceEngine(profile=profile or AudioProfile.default())
    if os.environ.get("SUG_ENABLE_BASS_FALLBACK") != "1":
        raise AudioPlaybackError("BASS preview fallback is disabled")
    try:
        from .bass_tsm_engine import BassTsmEngine

        return BassTsmEngine()
    except (ImportError, OSError) as error:
        raise AudioPlaybackError("BASS preview fallback is unavailable") from error
