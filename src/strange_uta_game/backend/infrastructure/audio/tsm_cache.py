"""磁盘缓存 TSM 渲染缓存。

设计：
- 切换播放速度（≠ 1.0x）时，后台 worker 用 Pedalboard 的 time_stretch 渲染，
  结果保存到磁盘缓存文件，不占用大量内存。
- 播放时从磁盘缓存读取到内存（只读取当前需要的部分）。
- 缓存文件位于用户目录下的 .cache 文件夹，更换歌曲或退出时自动清理。
- 1.0x 特殊路径：直接返回原始 PCM 引用，零渲染开销。

缓存文件命名：{歌曲名}_{speed}x.cache
"""

from __future__ import annotations

import os
import threading
import time
from pathlib import Path
from typing import Callable, Optional

import numpy as np
import soundfile as sf
from pedalboard import time_stretch


ProgressCallback = Callable[[float, float], None]  # (speed, 0.0~1.0)
DoneCallback = Callable[[float], None]              # (speed,)

_SPEED_QUANT = 2  # round(speed, 2)，0.01 精度
_CACHE_DIR_NAME = ".cache"


def _quantize(speed: float) -> float:
    return round(float(speed), _SPEED_QUANT)


def _get_cache_dir() -> Path:
    """获取缓存目录（软件工作目录下的 .cache 文件夹）"""
    cache_dir = Path.cwd() / _CACHE_DIR_NAME
    cache_dir.mkdir(parents=True, exist_ok=True)
    return cache_dir


def _get_cache_path(song_name: str, speed: float) -> Path:
    """获取缓存文件路径"""
    cache_dir = _get_cache_dir()
    q = _quantize(speed)
    filename = f"{song_name}_{q}x.cache"
    return cache_dir / filename


def clear_cache() -> None:
    """清空所有缓存文件"""
    cache_dir = _get_cache_dir()
    for f in cache_dir.glob("*.cache"):
        try:
            f.unlink()
        except Exception:
            pass
    print(f"[TSM] Cache cleared: {cache_dir}")


def clear_cache_for_song(song_name: str) -> None:
    """清空指定歌曲的所有缓存文件"""
    cache_dir = _get_cache_dir()
    for f in cache_dir.glob(f"{song_name}_*.cache"):
        try:
            f.unlink()
        except Exception:
            pass
    print(f"[TSM] Cache cleared for song: {song_name}")


class TSMRenderCache:
    """磁盘缓存 TSM 渲染缓存。"""

    def __init__(self) -> None:
        self._original: Optional[np.ndarray] = None  # (n, channels)
        self._sample_rate: int = 0
        self._channels: int = 0
        self._song_name: str = ""  # 歌曲名称（用于缓存文件命名）

        self._worker: Optional[threading.Thread] = None
        self._worker_cancel = threading.Event()
        self._worker_speed: Optional[float] = None
        self._render_version: int = 0
        self._lock = threading.Lock()

    # ---------- 加载 ----------

    def set_source(
        self,
        song_name: str,
        original_pcm: np.ndarray,
        sample_rate: int,
    ) -> None:
        """切换原始音频。清空旧缓存。"""
        self._cancel_worker_and_wait()
        with self._lock:
            self._song_name = song_name
            self._original = original_pcm
            self._sample_rate = int(sample_rate)
            self._channels = int(original_pcm.shape[1]) if original_pcm.ndim > 1 else 1
            # 清空旧缓存
            clear_cache_for_song(song_name)

    def clear(self) -> None:
        self._cancel_worker_and_wait()
        with self._lock:
            if self._song_name:
                clear_cache_for_song(self._song_name)

    # ---------- 查询 ----------

    def get(self, speed: float) -> Optional[np.ndarray]:
        """从磁盘缓存读取。命中返回 ndarray；未命中返回 None。"""
        if self._original is None:
            return None
        q = _quantize(speed)
        if abs(q - 1.0) < 1e-9:
            return self._original  # 1.0x 直通

        cache_path = _get_cache_path(self._song_name, q)
        if cache_path.exists():
            try:
                data, sr = sf.read(str(cache_path), dtype="float32")
                if data.ndim == 1:
                    data = data.reshape(-1, 1)
                return data
            except Exception as e:
                print(f"[TSM] Failed to read cache: {e}")
        return None

    # ---------- 渲染 ----------

    def ensure(
        self,
        speed: float,
        progress_cb: Optional[ProgressCallback] = None,
        done_cb: Optional[DoneCallback] = None,
    ) -> Optional[np.ndarray]:
        """确保 ``speed`` 对应的 PCM 就绪。

        - 若已缓存：立即返回 ndarray。
        - 否则：后台开始渲染，返回 ``None``；完成时调 ``done_cb(speed)``。
        """
        if self._original is None:
            return None
        q = _quantize(speed)
        if abs(q - 1.0) < 1e-9:
            return self._original

        # 检查磁盘缓存
        cached = self.get(q)
        if cached is not None:
            print(f"[TSM] Cache hit for speed {q}x")
            return cached

        # 需要渲染
        with self._lock:
            if self._worker is not None and self._worker_speed == q and self._worker.is_alive():
                print(f"[TSM] Already rendering speed {q}x, skipping")
                return None

        self._cancel_worker_and_wait()

        # 使用版本号控制取消
        self._render_version += 1
        current_version = self._render_version
        self._worker_speed = q
        print(f"[TSM] Starting render for speed {q}x, version={current_version}")

        def _target() -> None:
            try:
                print(f"[TSM] Worker started for speed {q}x, version={current_version}")
                rendered = self._render_full(q, progress_cb, current_version)
                if rendered is None:
                    print(f"[TSM] Render cancelled for speed {q}x, version={current_version}")
                    return

                # 保存到磁盘缓存
                cache_path = _get_cache_path(self._song_name, q)
                sf.write(str(cache_path), rendered, self._sample_rate)
                print(f"[TSM] Render complete for speed {q}x, saved to {cache_path}")

                if done_cb is not None:
                    try:
                        done_cb(q)
                    except Exception as e:
                        print(f"[TSM] done_cb error: {e}")
            except Exception as e:
                print(f"[TSM] Render error for speed {q}x: {e}")

        t = threading.Thread(target=_target, daemon=True, name=f"TSMRender-{q}")
        self._worker = t
        t.start()
        return None

    # ---------- 内部 ----------

    def _cancel_worker_and_wait(self) -> None:
        """取消正在进行的渲染任务。"""
        self._worker_cancel.set()
        self._worker = None
        self._worker_speed = None

    def _render_full(
        self,
        speed: float,
        progress_cb: Optional[ProgressCallback],
        render_version: int = 0,
    ) -> Optional[np.ndarray]:
        """整文件 TSM 渲染；返回 ``(n_samples, channels)`` float32。"""
        assert self._original is not None
        n_in = self._original.shape[0]
        if n_in == 0:
            return np.zeros((0, self._channels), dtype=np.float32)

        # 检查是否被取消
        if self._render_version != render_version:
            return None

        if progress_cb is not None:
            try:
                progress_cb(speed, 0.01)
            except Exception:
                pass

        # stretch_factor: >1 压缩（变快），<1 拉伸（变慢）
        stretch_factor = speed

        # 整文件处理
        pcm = np.ascontiguousarray(self._original, dtype=np.float32)
        out = time_stretch(pcm, float(self._sample_rate), stretch_factor=stretch_factor)

        if self._render_version != render_version:
            return None

        if progress_cb is not None:
            try:
                progress_cb(speed, 1.0)
            except Exception:
                pass

        return out.astype(np.float32)
