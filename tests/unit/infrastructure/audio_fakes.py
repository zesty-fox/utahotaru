from __future__ import annotations

import numpy as np


class FakeStatus:
    output_underflow = False

    def __bool__(self) -> bool:
        return False


class FakeOutputStream:
    def __init__(self, *, latency: float, callback, channels: int, **kwargs):
        self.latency = latency
        self.callback = callback
        self.channels = channels
        self.active = False

    def start(self) -> None:
        self.active = True

    def stop(self) -> None:
        self.active = False

    def close(self) -> None:
        self.active = False

    def invoke(self, frames: int) -> np.ndarray:
        output = np.zeros((frames, self.channels), dtype=np.float32)
        self.callback(output, frames, None, FakeStatus())
        return output


class FakeStreamFactory:
    def __init__(self, latency: float = 0.02):
        self.latency = latency
        self.streams: list[FakeOutputStream] = []

    def __call__(self, **kwargs) -> FakeOutputStream:
        stream = FakeOutputStream(latency=self.latency, **kwargs)
        self.streams.append(stream)
        return stream
