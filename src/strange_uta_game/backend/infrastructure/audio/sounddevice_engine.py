"""SoundDevice 音频引擎（离线预渲染 + RingBuffer 架构）。

设计目标：
彻底消除"回调线程跑 Python WSOLA + 持锁 + 大 blocksize"导致的爆音/卡顿/
左右声道交替伪像。

架构分三层：

1. :class:`TSMRenderCache`：UI/控制线程在切换速度时**离线**把整段原始 PCM
   预渲染成目标速度的 PCM，缓存在内存里（LRU 3 份）。1.0x 直接复用原始
   PCM，零开销。

2. :class:`RingBuffer`：单生产者单消费者无锁环形缓冲（float32 (n, ch)），
   生产者把"已渲染好的 PCM"按时间顺序填进去，消费者（回调）按 frames
   取出。

3. **Producer 线程**：tight loop 把 ``_active_pcm[_read_pos:]`` 里的样本
   切片送进 ring；监控用户的速度切换/seek 请求，在合适时机原子地把
   ``_active_pcm`` 替换成新速度的预渲染结果（保位 = 把当前位置的
   "原始时间轴"映射到新 PCM 上）。

4. **音频回调**：极简——只调 ``ring.read_into(outdata)``，不足补零，
   零分配、零锁、零 Python 重活。

位置语义保持不变：
- 对外暴露的 ``position_ms`` 始终指**原始音频时间轴**（不随速度伸缩）。
- 内部 ``_read_pos_samples`` 是当前 active PCM 上的偏移；位置查询时通过
  ``_read_pos_samples / _active_speed`` 还原到原始时间轴。
"""

from __future__ import annotations

import threading
import time
from pathlib import Path
from typing import Callable, Optional

import numpy as np
import sounddevice as sd
import soundfile as sf

from .base import (
    AudioInfo,
    AudioLoadError,
    AudioPlaybackError,
    IAudioEngine,
    PlaybackState,
)
from .ring_buffer import RingBuffer
from .tsm_cache import TSMRenderCache, LoadProgressCallback, _quantize


# ---- 常量 ----

# 回调块大小：1024 帧（@ 44.1kHz ≈ 23ms），远小于旧版 4410（100ms），
# 显著降低 underrun 概率与延迟。
_BLOCK_FRAMES = 1024

# Ring buffer 容量：~500ms 缓冲，足以吸收任何 GIL/调度抖动。
_RING_SECONDS = 0.5

# Producer tick：达到目标余量后睡眠的间隔（秒）
_PRODUCER_TICK = 0.005


class SoundDeviceEngine(IAudioEngine):
    """音频引擎（离线预渲染 + RingBuffer）。"""

    # 位置回调频率：60fps
    CALLBACK_INTERVAL = 0.016

    def __init__(self) -> None:
        # ---- 音频元数据 ----
        self._original_data: Optional[np.ndarray] = None  # (n, channels) float32（原始文件，仅用于波形显示）
        self._original_sample_rate: int = 44100  # 原始文件采样率（用于时长/位置计算）
        self._sample_rate: int = 44100  # 播放采样率（MP3 采样率，用于 stream/ring）
        self._channels: int = 2
        self._file_path: Optional[str] = None
        self._duration_ms: int = 0

        # ---- 播放状态 ----
        self._state = PlaybackState.STOPPED
        self._speed: float = 1.0
        self._volume: float = 1.0

        # ---- 渲染缓存 ----
        self._cache = TSMRenderCache()

        # ---- Active PCM（producer 当前在喂的那一份）----
        # 不可变快照：切换 active 时整体替换 (pcm, speed)
        self._active_pcm: Optional[np.ndarray] = None  # (n, channels)
        self._active_speed: float = 1.0
        self._read_pos_samples: int = 0  # 在 active_pcm 上的偏移

        # ---- 速度切换请求 ----
        # producer 检测到 _pending_speed != _active_speed 时，若新速度的
        # PCM 已就绪则立即原子换 active；否则先 ensure() 触发后台渲染，
        # 渲染完成后再换。
        self._pending_speed: float = 1.0

        # ---- Ring buffer（在 load 后按 channels 重建）----
        self._ring: Optional[RingBuffer] = None

        # ---- 线程 ----
        self._producer_thread: Optional[threading.Thread] = None
        self._producer_stop = threading.Event()
        # active 切换/seek 时 producer 必须暂停喂数据并 reset ring
        # _state_lock 只保护 producer 的"控制平面"（active/pos/pending），
        # 回调线程从不持此锁。
        self._state_lock = threading.Lock()

        self._stream: Optional[sd.OutputStream] = None

        # ---- 热重载标志位 ----
        # 当音频回调检测到底层设备异常时置位，由 producer 线程执行恢复
        self._needs_recovery = threading.Event()

        # ---- 位置回调 ----
        self._position_callback: Optional[Callable[[int], None]] = None
        self._callback_thread: Optional[threading.Thread] = None
        self._callback_stop = threading.Event()

        # ---- 渲染进度回调 ----
        # 签名 ``(speed, progress∈[0,1])``；progress=1.0 表示已就绪/切换完成。
        # 可能从 TSMRenderCache 的 worker 线程调用——UI 侧需自行 marshal。
        self._render_progress_cb: Optional[Callable[[float, float], None]] = None

    # ==================== 加载 / 资源 ====================

    def load(self, file_path: str, progress_cb: Optional[LoadProgressCallback] = None) -> None:
        # 加载新音频前，彻底停止并销毁旧的流和线程，防止"幽灵流"叠加导致倍速播放
        self.stop()

        try:
            if progress_cb:
                progress_cb("读取音频文件...", 0.0)
            data, sr = sf.read(file_path, dtype="float32")
            if data.ndim == 1:
                data = data.reshape(-1, 1)

            self._original_sample_rate = int(sr)
            self._channels = int(data.shape[1])
            self._file_path = file_path
            self._original_data = np.ascontiguousarray(data, dtype=np.float32)

            # 获取歌曲名称（不含扩展名）用于缓存文件命名
            song_name = Path(file_path).stem
            self._cache.set_source(song_name, self._original_data, self._original_sample_rate, progress_cb)

            # 从缓存获取 MP3 后的 PCM
            cached_pcm = self._cache.get(1.0)
            if cached_pcm is not None:
                self._sample_rate = self._cache._sample_rate
                self._channels = self._cache._channels
            else:
                self._sample_rate = self._original_sample_rate
                cached_pcm = self._original_data

            # 时长基于 MP3 实际数据（确保位置计算一致）
            self._duration_ms = int(len(cached_pcm) / self._sample_rate * 1000)

            # 重建 ring
            cap = max(_BLOCK_FRAMES * 4, int(_RING_SECONDS * self._sample_rate))
            self._ring = RingBuffer(cap, self._channels)

            with self._state_lock:
                self._active_pcm = cached_pcm
                self._active_speed = 1.0
                self._speed = 1.0
                self._pending_speed = 1.0
                self._read_pos_samples = 0

            self._state = PlaybackState.STOPPED

            # 预渲染常用速度（后台进行，不阻塞加载）
            self._prewarm_common_speeds()

        except FileNotFoundError:
            raise AudioLoadError(f"文件不存在: {file_path}")
        except Exception as e:
            raise AudioLoadError(f"加载音频失败: {e}")

    def _prewarm_common_speeds(self) -> None:
        """预渲染常用速度到磁盘缓存（后台进行，不阻塞加载）"""
        if self._original_data is None:
            return

        # 预渲染速度列表（按优先级排序，优先级越小越优先）
        common_speeds = [
            (0.75, 0),  # 最高优先级
            (0.5, 1),   # 第二优先级
            (0.9, 2),
            (0.8, 3),
            (0.7, 4),
            (0.6, 5),
        ]
        print(f"[SoundDeviceEngine] Prewarming common speeds: {[s for s, _ in common_speeds]}")
        for speed, priority in common_speeds:
            self._cache.ensure(speed, priority=priority)

    def release(self) -> None:
        self.stop()
        self._cache.clear()
        with self._state_lock:
            self._original_data = None
            self._active_pcm = None
            self._file_path = None
            self._duration_ms = 0
            self._read_pos_samples = 0
        self._ring = None

    # ==================== 播放控制 ====================

    def play(self) -> None:
        if self._original_data is None:
            raise AudioPlaybackError("没有加载音频文件")

        if self._state == PlaybackState.PLAYING:
            return

        if self._state == PlaybackState.PAUSED:
            self._state = PlaybackState.PLAYING
            return

        # 启动流 + producer
        # 先强制对齐 active 速度，避免 producer 启动后仍在喂旧速度数据
        self._maybe_swap_active_speed()
        self._start_streaming()
        self._state = PlaybackState.PLAYING

        if self._position_callback and (
            self._callback_thread is None or not self._callback_thread.is_alive()
        ):
            self._callback_stop.clear()
            self._callback_thread = threading.Thread(
                target=self._callback_loop, daemon=True, name="AudioPosCb"
            )
            self._callback_thread.start()

    def pause(self) -> None:
        if self._state == PlaybackState.PLAYING:
            self._state = PlaybackState.PAUSED
            # 不停 stream/producer，回调里检测 PAUSED 直接静音输出

    def stop(self) -> None:
        self._state = PlaybackState.STOPPED
        self._stop_streaming()
        self._callback_stop.set()
        if self._callback_thread and self._callback_thread.is_alive():
            self._callback_thread.join(timeout=0.5)
        self._callback_thread = None

        with self._state_lock:
            self._read_pos_samples = 0
            if self._original_data is not None:
                # 始终让 active 与当前速度保持一致
                if abs(self._speed - 1.0) < 1e-9:
                    self._active_pcm = self._cache.get(1.0)
                    self._active_speed = 1.0
                else:
                    cached = self._cache.get(self._speed)
                    if cached is not None:
                        self._active_pcm = cached
                        self._active_speed = self._speed
                    else:
                        self._active_pcm = self._cache.get(1.0)
                        self._active_speed = 1.0
                        self._speed = 1.0
                        self._pending_speed = 1.0

    # ==================== 位置 ====================

    def get_position_ms(self) -> int:
        with self._state_lock:
            if self._active_pcm is None or self._sample_rate == 0:
                return 0
            # pedalboard 输出的 PCM 是变速后的，长度不同
            # 播放变速后 PCM 的 N 个采样 = 原始时间轴 N * speed 个采样
            # 因为变速后 PCM 长度 = 原始长度 / speed
            read_pos = self._read_pos_samples

            # 减去 RingBuffer 中尚未播放的样本数，得到实际播放位置
            if self._ring is not None and self._state == PlaybackState.PLAYING:
                buffered_frames = self._ring.available_read()
                read_pos = max(0, read_pos - buffered_frames)

            # 位置计算：read_pos * active_speed = 原始时间轴上的采样位置
            orig_samples = read_pos * self._active_speed
            ms = int(orig_samples / self._sample_rate * 1000)
            return min(max(ms, 0), self._duration_ms)

    def set_position_ms(self, position_ms: int) -> None:
        if self._original_data is None:
            return
        position_ms = max(0, min(position_ms, self._duration_ms))
        orig_samples = int(position_ms / 1000 * self._sample_rate)
        self._seek_to_orig_samples(orig_samples)

    def _seek_to_orig_samples(self, orig_samples: int) -> None:
        """把播放头移到原始时间轴 ``orig_samples`` 处。"""
        with self._state_lock:
            if self._active_pcm is None or self._active_speed <= 0:
                return
            # 原始时间轴偏移 → 变速后 PCM 偏移
            # read_pos = orig_samples / active_speed
            new_pos = int(orig_samples / self._active_speed)
            new_pos = max(0, min(new_pos, len(self._active_pcm)))
            self._read_pos_samples = new_pos
        # 丢弃 ring 里的旧样本
        if self._ring is not None:
            self._ring.reset()

    def get_duration_ms(self) -> int:
        return self._duration_ms

    # ==================== 状态查询 ====================

    def get_playback_state(self) -> PlaybackState:
        return self._state

    def is_playing(self) -> bool:
        return self._state == PlaybackState.PLAYING

    # ==================== 速度 ====================

    def set_speed(self, speed: float) -> None:
        """切换速度。

        - 同步更新 ``self._speed`` 与 ``_pending_speed``。
        - 若新速度的 PCM 已在缓存里，producer 在下一 tick 即原子切换；
          否则触发后台渲染，**继续用当前速度播放**直到渲染完成（无缝切）。
        - 永远非阻塞。
        """
        if not 0.5 <= speed <= 2.0:
            raise ValueError(f"速度 {speed} 超出范围 [0.5, 2.0]")
        self._speed = float(speed)

        with self._state_lock:
            self._pending_speed = self._speed

        # 触发后台渲染（如已缓存或 1.0x 则立即返回 ndarray，producer 下一
        # tick 会自动 pickup；这里不在 UI 线程做切换以避免持锁等待）
        if self._original_data is not None:
            q = _quantize(self._speed)
            cb = self._render_progress_cb
            result = self._cache.ensure(
                self._speed,
                progress_cb=cb,
            )
            # 命中缓存 / 1.0x 直通：立刻通知 UI "已就绪"
            if result is not None and cb is not None:
                try:
                    cb(q, 1.0)
                except Exception:
                    pass

    def get_speed(self) -> float:
        return self._speed

    # ==================== 音量 ====================

    def set_volume(self, volume: float) -> None:
        self._volume = max(0.0, min(1.0, float(volume)))

    def get_volume(self) -> float:
        return self._volume

    # ==================== 回调注册 ====================

    def set_position_callback(self, callback: Callable[[int], None]) -> None:
        self._position_callback = callback
        if self._state == PlaybackState.PLAYING and (
            self._callback_thread is None or not self._callback_thread.is_alive()
        ):
            self._callback_stop.clear()
            self._callback_thread = threading.Thread(
                target=self._callback_loop, daemon=True, name="AudioPosCb"
            )
            self._callback_thread.start()

    def clear_position_callback(self) -> None:
        self._position_callback = None

    def set_render_progress_callback(
        self, callback: Optional[Callable[[float, float], None]]
    ) -> None:
        """注册渲染进度回调。

        签名 ``(speed, progress)``；``progress`` ∈ [0, 1]，1.0 表示已就绪。
        **注意**：回调可能在 TSMRenderCache 的 worker 线程被调用，UI 侧
        需通过 Qt 信号或 ``QMetaObject.invokeMethod`` marshal 到主线程。
        """
        self._render_progress_cb = callback

    def get_audio_info(self) -> Optional[AudioInfo]:
        if self._file_path is None:
            return None
        return AudioInfo(
            file_path=self._file_path,
            duration_ms=self._duration_ms,
            sample_rate=self._sample_rate,
            channels=self._channels,
        )

    def get_original_samples(self) -> Optional[np.ndarray]:
        """获取音频采样数据（用于波形可视化）

        Returns:
            MP3 后的 PCM 数据，形状为 (n_samples, channels) 的 float32 数组，
            采样率与播放采样率一致。如果没有加载音频则返回 None
        """
        return self._cache.get(1.0)

    # ==================== 内部：流 / Producer / 回调 ====================

    def _start_streaming(self) -> None:
        """启动 PortAudio stream + producer 线程。"""
        if self._ring is None or self._original_data is None:
            return

        # 防御性清理：绝对不允许同一个实例开启两个 stream
        self._stop_streaming()

        # 启动 producer
        self._producer_stop.clear()
        self._producer_thread = threading.Thread(
            target=self._producer_loop, daemon=True, name="AudioProducer"
        )
        self._producer_thread.start()

        # 启动 stream
        try:
            self._stream = sd.OutputStream(
                samplerate=self._sample_rate,
                channels=self._channels,
                dtype="float32",
                blocksize=_BLOCK_FRAMES,
                callback=self._audio_callback,
            )
            self._stream.start()
        except Exception as e:
            print(f"[SoundDeviceEngine] open stream failed: {e}")
            self._producer_stop.set()
            self._stream = None

    def _stop_streaming(self) -> None:
        # 先停 stream（保证回调不再被调用）
        if self._stream is not None:
            try:
                self._stream.stop()
                self._stream.close()
            except Exception:
                pass
            self._stream = None

        # 再停 producer
        self._producer_stop.set()
        if self._producer_thread and self._producer_thread.is_alive():
            self._producer_thread.join(timeout=1.0)
        self._producer_thread = None

        if self._ring is not None:
            self._ring.reset()

    def _audio_callback(self, outdata, frames, time_info, status) -> None:  # noqa: D401
        """**实时回调**：极简、零分配、零锁、零 Python 重活。"""
        if status:
            if status.output_underflow:
                # underflow 只是说明 Python 喂数据慢了，属于正常性能抖动，不用管
                pass
            else:
                # 遇到了设备断开、采样率突变等致命状态
                print(f"[SoundDeviceEngine] 底层设备状态异常，请求热重载: {status}")
                self._needs_recovery.set()
                outdata.fill(0)
                return

        if self._state != PlaybackState.PLAYING:
            outdata.fill(0)
            return

        ring = self._ring
        if ring is None:
            outdata.fill(0)
            return

        n = ring.read_into(outdata)
        if n < frames:
            # underrun：补零，不抛错（旧版会触发 PortAudio 错位）
            outdata[n:].fill(0)

        if self._volume != 1.0:
            outdata *= self._volume

    def _producer_loop(self) -> None:
        """生产者：把 active PCM 切片送进 ring；处理速度切换 / EOF。"""
        if self._ring is None:
            return

        # 目标余量：保持 ring 至少有 _BLOCK_FRAMES * 2 帧可读
        target_low = _BLOCK_FRAMES * 2

        while not self._producer_stop.is_set():
            # 0) 看门狗：检测是否需要热重载 (设备切换、流崩溃或抛出异常)
            if self._state == PlaybackState.PLAYING and self._stream is not None:
                if self._needs_recovery.is_set() or not self._stream.active:
                    self._perform_hot_recovery()
                    continue

            # 1) 检查待切换的速度
            self._maybe_swap_active_speed()

            # 2) 暂停时停止喂数据（让 ring 自然耗尽 → 回调输出零）
            if self._state == PlaybackState.PAUSED:
                time.sleep(_PRODUCER_TICK)
                continue

            # 3) 喂数据
            with self._state_lock:
                pcm = self._active_pcm
                pos = self._read_pos_samples
                speed = self._active_speed
                total = 0 if pcm is None else len(pcm)

            if pcm is None:
                time.sleep(_PRODUCER_TICK)
                continue

            free = self._ring.available_write()
            if free < target_low:
                time.sleep(_PRODUCER_TICK)
                continue

            remaining = total - pos
            if remaining <= 0:
                # EOF：自动停止
                self._on_eof()
                break

            chunk_n = min(free, remaining)
            chunk = pcm[pos : pos + chunk_n]
            written = self._ring.write_from(chunk)
            if written > 0:
                with self._state_lock:
                    # 仅当 active 没被换掉时才推进 pos
                    if self._active_pcm is pcm:
                        self._read_pos_samples += written

    def _maybe_swap_active_speed(self) -> None:
        """如有 pending 速度切换且新 PCM 已就绪，原子换 active 并保位。"""
        with self._state_lock:
            pending = _quantize(self._pending_speed)
            current = _quantize(self._active_speed)
            if abs(pending - current) < 1e-9:
                return
            cur_pcm = self._active_pcm
            cur_pos = self._read_pos_samples
            cur_speed = self._active_speed

        # 检查缓存是否已就绪
        new_pcm = self._cache.get(pending)
        if new_pcm is None:
            return  # 还没渲染好，下次再试

        # 计算"当前原始时间轴位置" → 在新 PCM 上的偏移
        if cur_pcm is None or self._sample_rate == 0:
            return
        # orig_samples = read_pos * cur_speed（原始时间轴位置）
        orig_samples = cur_pos * cur_speed
        # 在新 PCM 上的位置 = orig_samples / pending
        new_pos = int(orig_samples / max(pending, 1e-6))
        new_pos = max(0, min(new_pos, len(new_pcm)))

        with self._state_lock:
            self._active_pcm = new_pcm
            self._active_speed = pending  # 使用用户设置的速度
            self._read_pos_samples = new_pos
            # 更新 pending_speed 为当前 speed，避免重复 swap
            self._pending_speed = self._speed

        # 不再 reset ring buffer，让新旧 PCM 平滑过渡
        # ring buffer 中的旧数据会被新数据自然覆盖

    def _on_eof(self) -> None:
        """active PCM 喂完了：等 ring 排空，置 STOPPED。"""
        # 等待 ring 自然排空（最多 1s）
        if self._ring is not None:
            t0 = time.time()
            while self._ring.available_read() > 0 and time.time() - t0 < 1.0:
                if self._producer_stop.is_set():
                    return
                time.sleep(_PRODUCER_TICK)
        self._state = PlaybackState.STOPPED

    def _perform_hot_recovery(self) -> None:
        """执行音频流热重载（断线重连）

        当检测到底层设备异常（如采样率突变、设备拔插）时，
        静默销毁旧流 -> 等待设备稳定 -> 创建新流 -> 恢复播放进度。
        整个过程对用户来说只是短暂卡顿，然后自动恢复正常。
        """
        print("[SoundDeviceEngine] 正在执行音频流热重载...")
        self._needs_recovery.clear()

        # 1. 记住当前的播放位置（毫秒）
        current_ms = self.get_position_ms()

        # 2. 强行销毁旧的异常流
        if self._stream is not None:
            try:
                self._stream.stop()
                self._stream.close()
            except Exception:
                pass
            self._stream = None

        # 3. 稍微等待，给操作系统和 PortAudio 留出切换默认音频端点的时间
        # (比如蓝牙切换协议通常需要几百毫秒)
        time.sleep(0.5)

        # 4. 尝试重新开启流并恢复进度
        if self._producer_stop.is_set():
            return

        try:
            self._stream = sd.OutputStream(
                samplerate=self._sample_rate,
                channels=self._channels,
                dtype="float32",
                blocksize=_BLOCK_FRAMES,
                callback=self._audio_callback,
            )
            self._stream.start()

            # 恢复播放头位置，内部会调用 self._ring.reset() 并清空旧的废弃缓冲
            self.set_position_ms(current_ms)

            print("[SoundDeviceEngine] 热重载成功！已恢复播放。")
        except Exception as e:
            print(f"[SoundDeviceEngine] 热重载失败: {e}")
            # 如果实在救不回来，暂停播放，让用户后续手动点击播放重试
            self._state = PlaybackState.PAUSED

    def _callback_loop(self) -> None:
        """位置回调线程（独立于音频回调，~60fps）。"""
        last = -1
        while not self._callback_stop.is_set():
            if self._state == PlaybackState.PLAYING and self._position_callback:
                pos = self.get_position_ms()
                if pos != last:
                    try:
                        self._position_callback(pos)
                    except Exception as e:
                        print(f"[SoundDeviceEngine] position_callback error: {e}")
                    last = pos
            time.sleep(self.CALLBACK_INTERVAL)
