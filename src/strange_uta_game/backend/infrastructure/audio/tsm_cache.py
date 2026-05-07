"""磁盘缓存 TSM 渲染缓存。

设计：
- 切换播放速度（≠ 1.0x）时，后台 worker 用 Pedalboard 的 time_stretch 渲染，
  结果保存到磁盘缓存文件，不占用大量内存。
- 播放时从磁盘缓存读取到内存（只读取当前需要的部分）。
- 缓存文件位于用户目录下的 .cache 文件夹，更换歌曲或退出时自动清理。
- 1.0x 特殊路径：直接返回原始 PCM 引用，零渲染开销。
- 缓存文件采用 MP3 格式压缩，节省磁盘空间。

缓存文件命名：{歌曲名}_{speed}x.mp3
"""

from __future__ import annotations

import heapq
import os
import threading
import time
from pathlib import Path
from typing import Callable, Optional

import numpy as np
import soundfile as sf
from pedalboard import time_stretch
from pedalboard.io import AudioFile


ProgressCallback = Callable[[float, float], None]  # (speed, 0.0~1.0)
DoneCallback = Callable[[float], None]              # (speed,)
LoadProgressCallback = Callable[[str, float], None]  # (stage, 0.0~1.0)

_SPEED_QUANT = 2  # round(speed, 2)，0.01 精度
_CACHE_DIR_NAME = ".cache"
_MP3_QUALITY = 128  # MP3 比特率 (kbps)


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
    filename = f"{song_name}_{q}x.mp3"
    return cache_dir / filename


def _get_source_mp3_path(song_name: str) -> Path:
    """获取源 MP3 文件路径"""
    cache_dir = _get_cache_dir()
    return cache_dir / f"{song_name}_source.mp3"


def clear_cache() -> None:
    """清空所有缓存文件"""
    cache_dir = _get_cache_dir()
    for f in cache_dir.glob("*.mp3"):
        try:
            f.unlink()
        except Exception:
            pass
    print(f"[TSM] Cache cleared: {cache_dir}")


def clear_cache_for_song(song_name: str) -> None:
    """清空指定歌曲的所有缓存文件（包括源 MP3）"""
    cache_dir = _get_cache_dir()
    for f in cache_dir.glob(f"{song_name}_*.mp3"):
        try:
            f.unlink()
        except Exception:
            pass
    # 也清理源 MP3
    source = cache_dir / f"{song_name}_source.mp3"
    if source.exists():
        try:
            source.unlink()
        except Exception:
            pass
    print(f"[TSM] Cache cleared for song: {song_name}")


class TSMRenderCache:
    """磁盘缓存 TSM 渲染缓存，支持多线程并行渲染和优先级队列。

    架构：加载时将原始音频保存为源 MP3，后续所有操作（播放、TSM 渲染）
    都从这份 MP3 读取，减少内存占用。
    """

    # 最大并发渲染线程数
    MAX_WORKERS = 2
    # MP3 支持的采样率，选择 44100 作为标准
    _MP3_TARGET_SR = 44100

    def __init__(self) -> None:
        self._source_mp3_path: Optional[Path] = None  # 源 MP3 文件路径
        self._sample_rate: int = 0       # MP3 的采样率（降采样后）
        self._channels: int = 0
        self._song_name: str = ""

        # 优先级队列：(优先级, 速度, 进度回调, 完成回调)
        self._render_queue: list = []
        self._queue_lock = threading.Lock()

        # 正在渲染的任务：{speed: thread}
        self._active_renders: dict[float, threading.Thread] = {}
        self._active_lock = threading.Lock()

        # 版本控制：用于取消所有任务
        self._render_version: int = 0
        self._lock = threading.Lock()

        # 调度线程
        self._scheduler_thread: Optional[threading.Thread] = None
        self._scheduler_stop = threading.Event()

    # ---------- 加载 ----------

    def set_source(
        self,
        song_name: str,
        original_pcm: np.ndarray,
        sample_rate: int,
        progress_cb: Optional[LoadProgressCallback] = None,
    ) -> None:
        """切换原始音频。将原始 PCM 保存为源 MP3，清空旧缓存。

        Args:
            song_name: 歌曲名称（用于缓存文件命名）
            original_pcm: (samples, channels) float32 原始 PCM 数据
            sample_rate: 原始采样率
            progress_cb: 加载进度回调 (stage, progress)
        """
        self._cancel_all_and_wait()
        with self._lock:
            self._song_name = song_name
            channels = int(original_pcm.shape[1]) if original_pcm.ndim > 1 else 1

            # 清空旧缓存
            if progress_cb:
                progress_cb("清理旧缓存...", 0.0)
            clear_cache_for_song(song_name)

            # 将原始 PCM 保存为源 MP3（可能需要降采样）
            if progress_cb:
                progress_cb("转换为 MP3...", 0.1)
            source_path = _get_source_mp3_path(song_name)
            actual_sr = self._save_source_as_mp3(
                original_pcm, sample_rate, channels, source_path, progress_cb
            )
            self._source_mp3_path = source_path
            self._sample_rate = actual_sr
            self._channels = channels

            if progress_cb:
                progress_cb("完成", 1.0)
            print(f"[TSM] Source MP3 saved: {source_path} ({actual_sr}Hz, {channels}ch)")

    def _save_source_as_mp3(
        self,
        pcm: np.ndarray,
        sample_rate: int,
        channels: int,
        path: Path,
        progress_cb: Optional[LoadProgressCallback] = None,
    ) -> int:
        """将 PCM 保存为 MP3，如果采样率不支持则降采样。

        Returns:
            实际保存的采样率
        """
        # MP3 支持的采样率
        mp3_rates = [32000, 44100, 48000]
        target_sr = sample_rate
        if sample_rate not in mp3_rates:
            target_sr = min(mp3_rates, key=lambda r: abs(r - sample_rate))
            print(f"[TSM] Resampling {sample_rate}Hz -> {target_sr}Hz for MP3")

        # 如果需要降采样
        data = pcm
        if target_sr != sample_rate:
            if progress_cb:
                progress_cb("降采样中...", 0.3)
            from pedalboard.io import StreamResampler
            resampler = StreamResampler(sample_rate, target_sr, channels)
            resampled = resampler.process(pcm.T)
            tail = resampler.process(None)
            resampled_full = np.concatenate([resampled, tail], axis=1)
            data = resampled_full.T.astype(np.float32)

        # 编码为 MP3
        if progress_cb:
            progress_cb("编码 MP3...", 0.6)
        mp3_bytes = AudioFile.encode(
            data.T,
            samplerate=target_sr,
            format="mp3",
            num_channels=channels,
            quality=_MP3_QUALITY,
        )
        if progress_cb:
            progress_cb("保存文件...", 0.9)
        with open(path, "wb") as f:
            f.write(mp3_bytes)

        return target_sr

    def clear(self) -> None:
        self._cancel_all_and_wait()
        with self._lock:
            if self._song_name:
                clear_cache_for_song(self._song_name)
            self._source_mp3_path = None

    # ---------- 查询 ----------

    def get(self, speed: float) -> Optional[np.ndarray]:
        """从磁盘缓存读取。命中返回 ndarray；未命中返回 None。"""
        if self._source_mp3_path is None:
            return None
        q = _quantize(speed)
        if abs(q - 1.0) < 1e-9:
            return self._load_source_pcm()  # 1.0x 从源 MP3 读取

        cache_path = _get_cache_path(self._song_name, q)
        if cache_path.exists():
            try:
                data = self._load_from_mp3(cache_path)
                return data
            except Exception as e:
                print(f"[TSM] Failed to read cache: {e}")
        return None

    def _load_source_pcm(self) -> Optional[np.ndarray]:
        """从源 MP3 加载 PCM 数据。

        Returns:
            (samples, channels) float32 数据，失败返回 None
        """
        if self._source_mp3_path is None or not self._source_mp3_path.exists():
            return None
        return self._load_from_mp3(self._source_mp3_path)

    def _load_from_mp3(self, path: Path) -> np.ndarray:
        """从 MP3 文件加载 PCM 数据。

        Returns:
            (samples, channels) float32 数据
        """
        with AudioFile(str(path)) as f:
            audio = f.read(f.frames)  # (channels, samples)
        return audio.T.astype(np.float32)

    # ---------- 渲染 ----------

    def ensure(
        self,
        speed: float,
        priority: int = 99,
        progress_cb: Optional[ProgressCallback] = None,
        done_cb: Optional[DoneCallback] = None,
    ) -> Optional[np.ndarray]:
        """确保 ``speed`` 对应的 PCM 就绪。

        - 若已缓存：立即返回 ndarray。
        - 否则：加入渲染队列，返回 ``None``；完成时调 ``done_cb(speed)``。
        """
        if self._source_mp3_path is None:
            return None
        q = _quantize(speed)
        if abs(q - 1.0) < 1e-9:
            return self._load_source_pcm()

        # 检查磁盘缓存
        cached = self.get(q)
        if cached is not None:
            print(f"[TSM] Cache hit for speed {q}x")
            return cached

        # 检查是否已在渲染或队列中
        with self._active_lock:
            if q in self._active_renders:
                print(f"[TSM] Already rendering speed {q}x, skipping")
                return None

        with self._queue_lock:
            for _, queued_speed, _, _ in self._render_queue:
                if abs(queued_speed - q) < 1e-9:
                    print(f"[TSM] Already queued for speed {q}x, skipping")
                    return None

        # 加入渲染队列
        with self._queue_lock:
            heapq.heappush(self._render_queue, (priority, q, progress_cb, done_cb))
            print(f"[TSM] Queued render for speed {q}x with priority {priority}")

        self._ensure_scheduler_running()
        return None

    # ---------- 内部 ----------

    def _ensure_scheduler_running(self) -> None:
        """确保调度线程在运行。"""
        with self._lock:
            if self._scheduler_thread is not None and self._scheduler_thread.is_alive():
                return
            self._scheduler_stop.clear()
            self._scheduler_thread = threading.Thread(
                target=self._scheduler_loop, daemon=True, name="TSMScheduler"
            )
            self._scheduler_thread.start()

    def _scheduler_loop(self) -> None:
        """调度线程：从队列中取出任务并执行。"""
        while not self._scheduler_stop.is_set():
            task = None
            with self._queue_lock:
                if self._render_queue:
                    task = heapq.heappop(self._render_queue)

            if task is None:
                with self._active_lock:
                    if not self._active_renders:
                        break
                time.sleep(0.1)
                continue

            priority, speed, progress_cb, done_cb = task

            with self._lock:
                current_version = self._render_version

            # 等待有空闲线程
            while not self._scheduler_stop.is_set():
                with self._active_lock:
                    if len(self._active_renders) < self.MAX_WORKERS:
                        break
                time.sleep(0.05)

            if self._scheduler_stop.is_set():
                break

            thread = threading.Thread(
                target=self._render_worker,
                args=(speed, progress_cb, done_cb, current_version),
                daemon=True,
                name=f"TSMRender-{speed}"
            )
            with self._active_lock:
                self._active_renders[speed] = thread
            thread.start()

    def _render_worker(
        self,
        speed: float,
        progress_cb: Optional[ProgressCallback],
        done_cb: Optional[DoneCallback],
        render_version: int,
    ) -> None:
        """渲染工作线程。"""
        try:
            print(f"[TSM] Worker started for speed {speed}x, version={render_version}")
            rendered = self._render_full(speed, progress_cb, render_version)
            if rendered is None:
                print(f"[TSM] Render cancelled for speed {speed}x, version={render_version}")
                return

            # 保存到磁盘缓存（MP3 格式）
            cache_path = _get_cache_path(self._song_name, speed)
            self._save_as_mp3(rendered, cache_path)
            print(f"[TSM] Render complete for speed {speed}x, saved to {cache_path}")

            if done_cb is not None:
                try:
                    done_cb(speed)
                except Exception as e:
                    print(f"[TSM] done_cb error: {e}")
        except Exception as e:
            print(f"[TSM] Render error for speed {speed}x: {e}")
        finally:
            with self._active_lock:
                self._active_renders.pop(speed, None)

    def _save_as_mp3(self, pcm: np.ndarray, path: Path) -> None:
        """将 PCM 数据保存为 MP3 文件。

        Args:
            pcm: (samples, channels) float32 数据（已经是 MP3 兼容采样率）
            path: 输出文件路径
        """
        mp3_bytes = AudioFile.encode(
            pcm.T,  # (channels, samples)
            samplerate=self._sample_rate,
            format="mp3",
            num_channels=self._channels,
            quality=_MP3_QUALITY,
        )
        with open(path, "wb") as f:
            f.write(mp3_bytes)

    def _cancel_all_and_wait(self) -> None:
        """取消所有渲染任务并等待完成。"""
        with self._lock:
            self._render_version += 1

        with self._queue_lock:
            self._render_queue.clear()

        self._scheduler_stop.set()
        if self._scheduler_thread and self._scheduler_thread.is_alive():
            self._scheduler_thread.join(timeout=2.0)
        self._scheduler_thread = None

        with self._active_lock:
            threads = list(self._active_renders.values())
        for t in threads:
            if t.is_alive():
                t.join(timeout=2.0)
        with self._active_lock:
            self._active_renders.clear()

    def _render_full(
        self,
        speed: float,
        progress_cb: Optional[ProgressCallback],
        render_version: int = 0,
    ) -> Optional[np.ndarray]:
        """整文件 TSM 渲染；返回 ``(n_samples, channels)`` float32。"""
        # 从源 MP3 读取 PCM
        source_pcm = self._load_source_pcm()
        if source_pcm is None:
            return None
        n_in = source_pcm.shape[0]
        if n_in == 0:
            return np.zeros((0, self._channels), dtype=np.float32)

        if self._render_version != render_version:
            return None

        if progress_cb is not None:
            try:
                progress_cb(speed, 0.01)
            except Exception:
                pass

        # 整文件处理
        pcm = np.ascontiguousarray(source_pcm, dtype=np.float32)
        out = time_stretch(pcm, float(self._sample_rate), stretch_factor=speed)

        if self._render_version != render_version:
            return None

        if progress_cb is not None:
            try:
                progress_cb(speed, 1.0)
            except Exception:
                pass

        return out.astype(np.float32)
