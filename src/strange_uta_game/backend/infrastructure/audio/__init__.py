"""Audio module."""

import sys

from .base import (
    AudioDiagnostics,
    AudioError,
    AudioInfo,
    AudioLoadError,
    AudioPlaybackError,
    IAudioEngine,
    PlaybackState,
)
from .profile import AudioProfile
from .factory import AudioBackend, create_audio_engine
from .sounddevice_engine import SoundDeviceEngine

class BassEngine:
    """Lazy compatibility constructor for the opt-in Windows BASS preview."""

    def __new__(cls, *args, **kwargs):
        if sys.platform != "win32":
            raise AudioPlaybackError("BASS audio backend is only available on Windows")
        from .bass_engine import BassEngine as Implementation

        return Implementation(*args, **kwargs)


class BassTsmEngine:
    """Lazy compatibility constructor for the opt-in BASS TSM preview."""

    def __new__(cls, *args, **kwargs):
        if sys.platform != "win32":
            raise AudioPlaybackError("BASS audio backend is only available on Windows")
        from .bass_tsm_engine import BassTsmEngine as Implementation

        return Implementation(*args, **kwargs)

__all__ = [
    "IAudioEngine",
    "AudioError",
    "AudioLoadError",
    "AudioPlaybackError",
    "PlaybackState",
    "AudioInfo",
    "AudioDiagnostics",
    "AudioProfile",
    "AudioBackend",
    "create_audio_engine",
    "SoundDeviceEngine",
    "BassEngine",
    "BassTsmEngine",
]
