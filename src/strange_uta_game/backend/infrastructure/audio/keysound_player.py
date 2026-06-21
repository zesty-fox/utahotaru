"""低延迟按键音播放器 — 基于 BASS Sample API。

BASS_SampleLoad 把 WAV 加载为"样本"，最多可同时持有 _MAX_CONCURRENT 个播放通道，
超出时自动复用最旧的通道（BASS_SAMPLE_OVER_POS）。每次 play_* 调用仅需
BASS_SampleGetChannel + BASS_ChannelPlay，无文件 IO，无内存分配，延迟极低。
"""

from __future__ import annotations

import ctypes
from pathlib import Path

from . import bass_available

try:
    from .bass_engine import (
        BASS_ATTRIB_VOL,
        BASS_DEVICE_LATENCY,
        BASS_ERROR_ALREADY,
        BASS_UNICODE,
        _bass,
    )
except (ImportError, OSError, AttributeError):
    # mac 等：bass_engine 不可导入（_DummyCDLL 抛 AttributeError）。KeySoundPlayer
    # 仅在 bass_available 为 True 时由工厂实例化，占位常量不会被实际使用。
    _bass = None  # type: ignore[assignment]
    BASS_ATTRIB_VOL = 0
    BASS_DEVICE_LATENCY = 0
    BASS_ERROR_ALREADY = -1
    BASS_UNICODE = 0

BASS_SAMPLE_OVER_POS: int = 0x400000  # 超出 max 时复用最旧（按播放位置）
_MAX_CONCURRENT: int = 8              # 每个音效最多同时播放数


class KeySoundPlayer:
    """低延迟按键音播放器，支持重叠播放，不互相打断。

    线程安全：BASS 内部线程安全，此类不加额外锁。
    """

    def __init__(self) -> None:
        self._press_sample: int = 0
        self._release_sample: int = 0
        self._enabled: bool = True
        self._volume: float = 1.0  # 0.0 ~ 2.0（对应 0 ~ 200%）

    def load(self, press_path: Path, release_path: Path) -> None:
        """加载按下音和抬起音。已有样本先释放。"""
        self.free()
        # BASS 是进程全局单例；若已由 BassEngine 初始化则 BASS_ERROR_ALREADY 正常
        if not _bass.BASS_Init(-1, 44100, BASS_DEVICE_LATENCY, None, None):
            if _bass.BASS_ErrorGetCode() != BASS_ERROR_ALREADY:
                return  # 初始化失败，静默跳过
        self._press_sample = self._load_sample(press_path)
        self._release_sample = self._load_sample(release_path)

    def _load_sample(self, path: Path) -> int:
        if not path.is_file():
            return 0
        return int(
            _bass.BASS_SampleLoad(
                False,
                ctypes.c_wchar_p(str(path)),
                0,
                0,
                _MAX_CONCURRENT,
                BASS_SAMPLE_OVER_POS | BASS_UNICODE,
            )
        )

    def play_press(self) -> None:
        """播放按下音（立即返回，不阻塞）。"""
        if not self._enabled or not self._press_sample:
            return
        try:
            chan = _bass.BASS_SampleGetChannel(self._press_sample, False)
            if chan:
                _bass.BASS_ChannelSetAttribute(chan, BASS_ATTRIB_VOL, ctypes.c_float(self._volume))
                _bass.BASS_ChannelPlay(chan, False)
        except Exception:
            pass

    def play_release(self) -> None:
        """播放抬起音（立即返回，不阻塞）。"""
        if not self._enabled or not self._release_sample:
            return
        try:
            chan = _bass.BASS_SampleGetChannel(self._release_sample, False)
            if chan:
                _bass.BASS_ChannelSetAttribute(chan, BASS_ATTRIB_VOL, ctypes.c_float(self._volume))
                _bass.BASS_ChannelPlay(chan, False)
        except Exception:
            pass

    def set_enabled(self, enabled: bool) -> None:
        self._enabled = enabled

    def set_volume(self, volume_pct: int) -> None:
        """设置音量，单位为百分比（0~200）。"""
        self._volume = max(0.0, min(2.0, volume_pct / 100.0))

    def invalidate(self) -> None:
        """BASS_Free 后调用：将 handle 归零，不再尝试 BASS_SampleFree。

        BASS_Free 已经回收了所有资源；若之后再用旧 handle 调用 BASS_SampleFree，
        可能误释放新 BASS 会话中复用了同一 handle 值的合法资源。
        """
        self._press_sample = 0
        self._release_sample = 0

    def is_loaded(self) -> bool:
        return bool(self._press_sample and self._release_sample)

    def free(self) -> None:
        """释放样本资源（BASS_Free 之后调用亦安全）。"""
        try:
            if self._press_sample:
                _bass.BASS_SampleFree(self._press_sample)
        except Exception:
            pass
        finally:
            self._press_sample = 0
        try:
            if self._release_sample:
                _bass.BASS_SampleFree(self._release_sample)
        except Exception:
            pass
        finally:
            self._release_sample = 0


# ── mac（BASS 不可用）回退实现 ──────────────────────────────────────────────

import sounddevice as _sd
import soundfile as _sf
import numpy as _np


class SoundDeviceKeySoundPlayer:
    """基于 sounddevice 的按键音播放器（mac 等无 BASS 平台使用）。

    与 :class:`KeySoundPlayer` 同接口：``load`` 预读 WAV 为 numpy 数组，
    ``play_*`` 调 ``sounddevice.play``。节拍器点击音对延迟容忍度高，per-call
    播放足够，不复刻主引擎的 ring buffer。
    """

    def __init__(self) -> None:
        self._press: tuple[_np.ndarray, int] | None = None  # (data, sample_rate)
        self._release: tuple[_np.ndarray, int] | None = None
        self._enabled: bool = True
        self._volume: float = 1.0  # 0.0 ~ 2.0

    def load(self, press_path: Path, release_path: Path) -> None:
        """加载按下音和抬起音；失败静默跳过。"""
        self._press = self._read(press_path)
        self._release = self._read(release_path)

    @staticmethod
    def _read(path: Path) -> tuple[_np.ndarray, int] | None:
        if not path.is_file():
            return None
        try:
            data, sr = _sf.read(str(path), dtype="float32")
            return data, sr
        except Exception:
            return None

    def _play(self, sample: tuple[_np.ndarray, int] | None) -> None:
        if not self._enabled or sample is None:
            return
        data, sr = sample
        try:
            _sd.play(data * self._volume, sr)
        except Exception:
            pass  # 设备忙/不可用时不打断主流程

    def play_press(self) -> None:
        self._play(self._press)

    def play_release(self) -> None:
        self._play(self._release)

    def set_enabled(self, enabled: bool) -> None:
        self._enabled = enabled

    def set_volume(self, volume_pct: int) -> None:
        self._volume = max(0.0, min(2.0, volume_pct / 100.0))

    def invalidate(self) -> None:
        """对齐 KeySoundPlayer 接口；sounddevice 无外部 handle 需失效。"""
        pass

    def is_loaded(self) -> bool:
        return self._press is not None and self._release is not None

    def free(self) -> None:
        self._press = None
        self._release = None


def create_keysound_player():
    """按 BASS 可用性选择 keysound 实现。"""
    if bass_available:
        return KeySoundPlayer()
    return SoundDeviceKeySoundPlayer()
