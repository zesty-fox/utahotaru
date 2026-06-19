"""Key sounds delegated to the active shared audio engine."""

from __future__ import annotations

from pathlib import Path

import soundfile as sf

from .base import IAudioEngine


class KeySoundPlayer:
    def __init__(self, engine: IAudioEngine) -> None:
        self._engine = engine
        self._enabled = True
        self._volume = 1.0

    def load(self, press_path: Path, release_path: Path) -> None:
        self.free()
        self._load_effect("press", press_path)
        self._load_effect("release", release_path)

    def _load_effect(self, name: str, path: Path) -> None:
        if not path.is_file():
            return
        samples, sample_rate = sf.read(path, dtype="float32", always_2d=True)
        self._engine.load_effect(name, samples, int(sample_rate))

    def play_press(self) -> None:
        if self._enabled:
            self._engine.trigger_effect("press", self._volume)

    def play_release(self) -> None:
        if self._enabled:
            self._engine.trigger_effect("release", self._volume)

    def set_enabled(self, enabled: bool) -> None:
        self._enabled = enabled

    def set_volume(self, volume_pct: int) -> None:
        self._volume = max(0.0, min(2.0, volume_pct / 100.0))

    def invalidate(self) -> None:
        self.free()

    def is_loaded(self) -> bool:
        return self._engine.has_effect("press") and self._engine.has_effect("release")

    def free(self) -> None:
        self._engine.clear_effects()
