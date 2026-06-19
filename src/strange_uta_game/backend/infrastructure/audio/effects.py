"""Preloaded effects mixed into the shared audio callback."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np


@dataclass
class _Voice:
    sample: np.ndarray | None = None
    offset: int = 0
    volume: float = 1.0
    generation: int = 0

    def clear(self) -> None:
        self.sample = None
        self.offset = 0
        self.volume = 1.0


class EffectMixer:
    """Bounded mixer whose callback path performs no dynamic allocation."""

    def __init__(self, channels: int, block_frames: int = 1024) -> None:
        self._channels = channels
        self._samples: dict[str, np.ndarray] = {}
        self._voices = [_Voice() for _ in range(8)]
        self._scratch = np.empty((block_frames, channels), dtype=np.float32)
        self._generation = 0

    def load(self, name: str, sample: np.ndarray) -> None:
        data = np.ascontiguousarray(sample, dtype=np.float32)
        if data.ndim != 2 or data.shape[1] != self._channels:
            raise ValueError(f"effect must have shape (frames, {self._channels})")
        self._samples[name] = data

    def has(self, name: str) -> bool:
        return name in self._samples

    def clear(self) -> None:
        self._samples.clear()
        for voice in self._voices:
            voice.clear()

    def trigger(self, name: str, volume: float = 1.0) -> None:
        sample = self._samples.get(name)
        if sample is None:
            return
        self._generation += 1
        voice = None
        oldest = self._voices[0]
        for item in self._voices:
            if item.sample is None:
                voice = item
                break
            if item.generation < oldest.generation:
                oldest = item
        if voice is None:
            voice = oldest
        voice.sample = sample
        voice.offset = 0
        voice.volume = max(0.0, float(volume))
        voice.generation = self._generation

    def mix_into(self, output: np.ndarray) -> None:
        if len(output) > len(self._scratch):
            raise ValueError("output exceeds configured effect block size")
        for voice in self._voices:
            sample = voice.sample
            if sample is None:
                continue
            count = min(len(output), len(sample) - voice.offset)
            if count > 0:
                np.multiply(
                    sample[voice.offset : voice.offset + count],
                    voice.volume,
                    out=self._scratch[:count],
                )
                np.add(output[:count], self._scratch[:count], out=output[:count])
                voice.offset += count
            if voice.offset >= len(sample):
                voice.clear()
        np.clip(output, -1.0, 1.0, out=output)
