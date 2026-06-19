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

if sys.platform == "win32":
    from .bass_engine import BassEngine
    from .bass_tsm_engine import BassTsmEngine
else:
    class BassEngine:
        """Compatibility export for the unavailable Windows BASS backend."""

        def __init__(self, *args, **kwargs) -> None:
            raise AudioPlaybackError("BASS audio backend is only available on Windows")


    class BassTsmEngine(BassEngine):
        """Compatibility export for the unavailable Windows BASS TSM backend."""

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
