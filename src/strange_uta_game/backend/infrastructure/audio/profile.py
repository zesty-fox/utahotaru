"""Platform-neutral tuning inputs for the shared audio engine."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class AudioProfile:
    block_frames: int = 1024
    ring_seconds: float = 0.5
    requested_latency_seconds: float = 0.1
    thread_priority: int | None = None

    @classmethod
    def default(cls) -> AudioProfile:
        return cls()
