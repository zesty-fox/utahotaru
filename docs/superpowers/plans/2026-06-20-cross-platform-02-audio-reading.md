# Shared Audio and Reading Providers Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make the optimized sounddevice pipeline and shared Japanese-reading fallback the default on every supported platform while preserving measured timing behavior.

**Architecture:** One `SoundDeviceEngine` owns decoding, TSM rendering, buffering, effects mixing, authoritative timing, and recovery. A data-only `AudioProfile` supplies measured device defaults without duplicating engine algorithms. Reading analysis uses one provider chain: optional WinRT followed by shared Sudachi and pykakasi.

**Tech Stack:** Python 3.13, sounddevice/PortAudio, soundfile, NumPy, pedalboard, SudachiPy, pykakasi, pytest

---

## File Map

- Modify `audio/base.py`: diagnostics and capabilities on the stable port.
- Modify `audio/sounddevice_engine.py`: injected stream factory/profile, timing diagnostics, effects mixer.
- Create `audio/profile.py`: platform-neutral audio profile and defaults.
- Create `audio/effects.py`: preallocated keysound mixer.
- Create `audio/factory.py`: shared default and preview-only BASS fallback.
- Modify `audio/keysound_player.py`: delegate to the active shared engine.
- Modify `frontend/main_window.py` and `frontend/editor/timing_interface.py`: consume injected audio services.
- Modify `parsers/ruby_analyzer.py`: provider chain and capability reporting.
- Create `scripts/audio_loopback_probe.py`: reproducible hardware measurement output.
- Extend infrastructure and application tests.

### Task 1: Characterize SoundDeviceEngine Without Real Hardware

**Files:**
- Modify: `src/strange_uta_game/backend/infrastructure/audio/sounddevice_engine.py:93-180`
- Create: `tests/unit/infrastructure/audio_fakes.py`
- Create: `tests/unit/infrastructure/test_sounddevice_engine.py`

- [ ] **Step 1: Write tests for load, seek, state, and original timeline**

```python
def test_position_stays_on_original_timeline(wav_file, fake_stream_factory):
    engine = SoundDeviceEngine(stream_factory=fake_stream_factory)
    engine.load(wav_file)
    engine.set_speed(0.5)
    engine.set_position_ms(500)
    assert engine.get_position_ms() == 500


def test_missing_file_raises_audio_load_error(fake_stream_factory):
    engine = SoundDeviceEngine(stream_factory=fake_stream_factory)
    with pytest.raises(AudioLoadError):
        engine.load("missing.wav")


def test_stop_resets_position(wav_file, fake_stream_factory):
    engine = SoundDeviceEngine(stream_factory=fake_stream_factory)
    engine.load(wav_file)
    engine.set_position_ms(500)
    engine.stop()
    assert engine.get_position_ms() == 0
```

`FakeOutputStream` must expose `latency`, `active`, `start()`, `stop()`,
`close()`, and `invoke(frames)`; `invoke` calls the captured callback with a
preallocated `float32` output array.

- [ ] **Step 2: Run tests and verify constructor failure**

Run: `pytest tests/unit/infrastructure/test_sounddevice_engine.py -v`

Expected: FAIL because `SoundDeviceEngine` does not accept `stream_factory`.

- [ ] **Step 3: Inject stream construction**

Add this constructor contract without changing production behavior:

```python
StreamFactory = Callable[..., sd.OutputStream]


def __init__(self, stream_factory: StreamFactory = sd.OutputStream) -> None:
    self._stream_factory = stream_factory
    # retain existing initialization
```

Replace the direct `sd.OutputStream(...)` call with
`self._stream_factory(...)`. Move reusable WAV fixture creation from the
BASS-only test into `tests/unit/infrastructure/conftest.py`.

- [ ] **Step 4: Run SoundDevice and existing audio tests**

Run: `pytest tests/unit/infrastructure/test_sounddevice_engine.py tests/unit/infrastructure/test_ring_buffer.py tests/unit/infrastructure/test_tsm_cache.py -v`

Expected: all tests pass without opening a host audio device.

- [ ] **Step 5: Commit**

```bash
git add src/strange_uta_game/backend/infrastructure/audio/sounddevice_engine.py tests/unit/infrastructure
git commit -m "test: characterize shared sounddevice engine"
```

### Task 2: Add Audio Profiles and Structured Diagnostics

**Files:**
- Create: `src/strange_uta_game/backend/infrastructure/audio/profile.py`
- Modify: `src/strange_uta_game/backend/infrastructure/audio/base.py`
- Modify: `src/strange_uta_game/backend/infrastructure/audio/sounddevice_engine.py`
- Test: `tests/unit/infrastructure/test_audio_profile.py`
- Test: `tests/unit/infrastructure/test_audio_diagnostics.py`

- [ ] **Step 1: Write profile and diagnostics tests**

```python
def test_default_profile_is_platform_neutral():
    profile = AudioProfile.default()
    assert profile.block_frames == 1024
    assert profile.ring_seconds == 0.5
    assert profile.requested_latency_seconds == 0.1
    assert profile.thread_priority is None


def test_diagnostics_report_requested_and_actual_latency(
    wav_file, fake_stream_factory
):
    fake_stream_factory.latency = 0.023
    engine = SoundDeviceEngine(stream_factory=fake_stream_factory)
    engine.load(wav_file)
    diagnostics = engine.get_diagnostics()
    assert diagnostics.actual_latency_ms == pytest.approx(23.0)
    assert diagnostics.block_frames == 1024
```

- [ ] **Step 2: Run tests and verify missing types**

Run: `pytest tests/unit/infrastructure/test_audio_profile.py tests/unit/infrastructure/test_audio_diagnostics.py -v`

Expected: FAIL because `AudioProfile` and `AudioDiagnostics` are undefined.

- [ ] **Step 3: Add the types and port method**

```python
@dataclass(frozen=True)
class AudioProfile:
    block_frames: int = 1024
    ring_seconds: float = 0.5
    requested_latency_seconds: float = 0.1
    thread_priority: int | None = None

    @classmethod
    def default(cls) -> "AudioProfile":
        return cls()


@dataclass(frozen=True)
class AudioDiagnostics:
    backend: str
    device: str
    sample_rate: int
    block_frames: int
    requested_latency_ms: float
    actual_latency_ms: float
    underruns: int
    recoveries: int
```

Add `get_diagnostics() -> AudioDiagnostics` to `IAudioEngine`. Replace module
constants in `SoundDeviceEngine` with the injected `AudioProfile`, count status
underruns and completed recovery attempts, and use `sd.query_hostapis()` only
when diagnostics are requested.

- [ ] **Step 4: Run tests**

Run: `pytest tests/unit/infrastructure/test_audio_profile.py tests/unit/infrastructure/test_audio_diagnostics.py tests/unit/infrastructure/test_sounddevice_engine.py -v`

Expected: all tests pass.

- [ ] **Step 5: Commit**

```bash
git add src/strange_uta_game/backend/infrastructure/audio tests/unit/infrastructure
git commit -m "feat: add audio profiles and diagnostics"
```

### Task 3: Replace BASS Key Sounds With a Shared Mixer

**Files:**
- Create: `src/strange_uta_game/backend/infrastructure/audio/effects.py`
- Modify: `src/strange_uta_game/backend/infrastructure/audio/sounddevice_engine.py:551-590`
- Modify: `src/strange_uta_game/backend/infrastructure/audio/keysound_player.py`
- Test: `tests/unit/infrastructure/test_audio_effects.py`

- [ ] **Step 1: Write deterministic mixer tests**

```python
def test_triggered_effect_is_mixed_and_clipped():
    mixer = EffectMixer(channels=2)
    mixer.load("press", np.full((4, 2), 0.75, dtype=np.float32))
    mixer.trigger("press", volume=1.0)
    output = np.full((4, 2), 0.5, dtype=np.float32)
    mixer.mix_into(output)
    np.testing.assert_allclose(output, 1.0)


def test_unknown_effect_is_noop():
    mixer = EffectMixer(channels=2)
    output = np.zeros((8, 2), dtype=np.float32)
    mixer.trigger("missing", volume=1.0)
    mixer.mix_into(output)
    assert not output.any()
```

- [ ] **Step 2: Run test and verify missing mixer**

Run: `pytest tests/unit/infrastructure/test_audio_effects.py -v`

Expected: FAIL because `EffectMixer` is missing.

- [ ] **Step 3: Implement a bounded preloaded mixer**

`EffectMixer` stores contiguous samples by name, keeps at most eight active
voices, allocates `_scratch` once at construction, and writes directly into the
callback's `outdata`. `trigger()` only publishes `(sample, offset, volume)` into
an eight-slot preallocated voice array; it does not open another audio device.

```python
def mix_into(self, output: np.ndarray) -> None:
    for voice in self._voices:
        if voice.sample is None:
            continue
        count = min(len(output), len(voice.sample) - voice.offset)
        if count > 0:
            np.multiply(
                voice.sample[voice.offset:voice.offset + count],
                voice.volume,
                out=self._scratch[:count],
            )
            np.add(output[:count], self._scratch[:count], out=output[:count])
            voice.offset += count
        if voice.offset >= len(voice.sample):
            voice.clear()
    np.clip(output, -1.0, 1.0, out=output)
```

`KeySoundPlayer` loads sound files with `soundfile`, resamples/channel-normalizes
through the engine helper, and calls `engine.trigger_effect("press")` or
`engine.trigger_effect("release")`. Remove imports of BASS functions.

- [ ] **Step 4: Run effects and editor settings tests**

Run: `pytest tests/unit/infrastructure/test_audio_effects.py tests/unit/frontend/test_timing_interface_seek.py tests/unit/frontend/test_settings_shortcut.py -v`

Expected: all tests pass and importing `keysound_player` does not load BASS.

- [ ] **Step 5: Commit**

```bash
git add src/strange_uta_game/backend/infrastructure/audio/effects.py src/strange_uta_game/backend/infrastructure/audio/sounddevice_engine.py src/strange_uta_game/backend/infrastructure/audio/keysound_player.py tests/unit/infrastructure/test_audio_effects.py
git commit -m "feat: mix key sounds in shared audio output"
```

### Task 4: Create the Shared Audio Factory and Make It the Default

**Files:**
- Create: `src/strange_uta_game/backend/infrastructure/audio/factory.py`
- Modify: `src/strange_uta_game/backend/infrastructure/audio/__init__.py`
- Modify: `src/strange_uta_game/frontend/main_window.py:83-93,664-715`
- Modify: `src/strange_uta_game/frontend/editor/timing_interface.py:268-321,1004-1008`
- Test: `tests/unit/infrastructure/test_audio_factory.py`
- Test: `tests/unit/frontend/test_main_window_audio_factory.py`

- [ ] **Step 1: Write factory selection tests**

```python
def test_factory_uses_sounddevice_for_stable_and_preview():
    assert isinstance(create_audio_engine(AudioBackend.SHARED), SoundDeviceEngine)


def test_bass_requires_explicit_preview_fallback(monkeypatch):
    monkeypatch.setenv("SUG_ENABLE_BASS_FALLBACK", "1")
    engine = create_audio_engine(AudioBackend.BASS_PREVIEW)
    assert engine.__class__.__name__ in {"BassEngine", "BassTsmEngine"}
```

- [ ] **Step 2: Run tests and verify missing factory**

Run: `pytest tests/unit/infrastructure/test_audio_factory.py -v`

Expected: FAIL because `audio.factory` is missing.

- [ ] **Step 3: Implement explicit backend construction**

```python
class AudioBackend(StrEnum):
    SHARED = "shared"
    BASS_PREVIEW = "bass_preview"


def create_audio_engine(
    backend: AudioBackend = AudioBackend.SHARED,
    profile: AudioProfile | None = None,
) -> IAudioEngine:
    if backend is AudioBackend.SHARED:
        return SoundDeviceEngine(profile=profile or AudioProfile.default())
    if os.environ.get("SUG_ENABLE_BASS_FALLBACK") != "1":
        raise AudioPlaybackError("BASS preview fallback is disabled")
    from .bass_tsm_engine import BassTsmEngine
    return BassTsmEngine()
```

Inject the factory into `MainWindow`; remove `_hq_speed_enabled()` as an engine
selector. Keep `audio.hq_speed_change` only as the shared engine's TSM-quality
preference. Pass the active engine to `KeySoundPlayer` instead of invalidating
BASS handles during an engine swap.

- [ ] **Step 4: Run focused and application tests**

Run: `pytest tests/unit/infrastructure/test_audio_factory.py tests/unit/frontend tests/unit/application/test_timing_service_on_key_changed.py tests/unit/application/test_calibration_service.py -v`

Expected: all tests pass with no BASS import on the shared path.

- [ ] **Step 5: Commit**

```bash
git add src/strange_uta_game/backend/infrastructure/audio src/strange_uta_game/frontend/main_window.py src/strange_uta_game/frontend/editor/timing_interface.py tests/unit
git commit -m "feat: make shared audio engine the default"
```

### Task 5: Normalize the Reading Provider Chain

**Files:**
- Modify: `src/strange_uta_game/backend/infrastructure/parsers/ruby_analyzer.py:536-930`
- Create: `tests/unit/infrastructure/test_ruby_provider_chain.py`
- Modify: `build.py:90-150`
- Modify: `requirements-variants.txt`

- [ ] **Step 1: Write provider-order and fallback tests**

```python
def test_windows_capability_preserves_winrt_first(monkeypatch):
    providers = build_provider_chain(winrt_available=True)
    assert [provider.name for provider in providers] == ["winrt", "sudachi", "pykakasi"]


def test_shared_chain_works_without_winrt():
    providers = build_provider_chain(winrt_available=False)
    assert [provider.name for provider in providers] == ["sudachi", "pykakasi"]


def test_provider_failure_falls_through():
    analyzer = ProviderChain((FailingProvider(), StubProvider("にほんご")))
    assert analyzer.get_reading("日本語") == "にほんご"
```

- [ ] **Step 2: Run tests and verify missing chain types**

Run: `pytest tests/unit/infrastructure/test_ruby_provider_chain.py -v`

Expected: FAIL because `ProviderChain` and `build_provider_chain` are missing.

- [ ] **Step 3: Implement one capability-driven chain**

Give every provider `name`, `available()`, `analyze()`, and `get_reading()`.
`create_analyzer()` builds the ordered chain from availability, without
checking a release variant. Catch provider-unavailable errors at the chain
boundary; do not catch malformed result errors.

Build packages always include Sudachi and pykakasi. Windows builds additionally
collect WinRT when installed; remove the `noWinIME` product variant while
retaining compatibility with its version string during update migration.

- [ ] **Step 4: Run all parser tests**

Run: `pytest tests/unit/infrastructure/test_ruby_provider_chain.py tests/unit/infrastructure/test_kanji_reading_split.py tests/unit/infrastructure/test_lyric_parser.py tests/unit/test_llm_ruby.py -v`

Expected: all tests pass with WinRT imports absent on non-Windows test hosts.

- [ ] **Step 5: Commit**

```bash
git add src/strange_uta_game/backend/infrastructure/parsers/ruby_analyzer.py tests/unit/infrastructure/test_ruby_provider_chain.py build.py requirements-variants.txt
git commit -m "refactor: use one reading provider chain"
```

### Task 6: Add Reproducible Audio Acceptance Measurement

**Files:**
- Create: `scripts/audio_loopback_probe.py`
- Create: `tests/unit/scripts/test_audio_loopback_probe.py`
- Modify: `README_DEV.md`

- [ ] **Step 1: Write pure signal-analysis tests**

```python
def test_detect_impulse_latency_ms():
    recorded = np.zeros(4800, dtype=np.float32)
    recorded[480] = 1.0
    assert detect_impulse_latency_ms(recorded, sample_rate=48000) == pytest.approx(10.0)


def test_acceptance_rejects_error_over_ten_ms():
    result = evaluate_measurements([8.0, 9.5, 10.1])
    assert not result.passed
    assert result.max_error_ms == 10.1
```

- [ ] **Step 2: Run tests and verify missing script API**

Run: `pytest tests/unit/scripts/test_audio_loopback_probe.py -v`

Expected: FAIL because the probe module is missing.

- [ ] **Step 3: Implement analysis and JSON report output**

The CLI records repeated generated impulses through selected input/output
devices, subtracts the configured calibration value, and writes:

```json
{
  "schema": 1,
  "backend": "Core Audio",
  "sample_rate": 48000,
  "block_frames": 1024,
  "errors_ms": [8.0, 9.5, 9.1],
  "max_error_ms": 9.5,
  "passed": true
}
```

Exit 0 only when every calibrated error is at most 10 ms. Device access stays
behind `record_measurements()` so signal analysis remains unit-testable.

- [ ] **Step 4: Run unit tests and a manual probe**

Run: `pytest tests/unit/scripts/test_audio_loopback_probe.py -v`

Expected: tests pass.

Run on each reference machine:
`python scripts/audio_loopback_probe.py --list-devices`, followed by
`python scripts/audio_loopback_probe.py --input DEVICE --output DEVICE --runs 20 --report audio-report.json`.

Expected: report schema 1; stable release candidate exits 0 with
`max_error_ms <= 10.0`.

- [ ] **Step 5: Commit**

```bash
git add scripts/audio_loopback_probe.py tests/unit/scripts/test_audio_loopback_probe.py README_DEV.md
git commit -m "test: add calibrated audio loopback gate"
```

## Completion Gate

Run:

```bash
pytest tests/unit/infrastructure tests/unit/application tests/unit/frontend -v
python scripts/check_platform_boundaries.py
```

Expected: all tests and the boundary check pass. Produce schema-1 loopback
reports on Windows WASAPI, macOS CoreAudio, and Linux PipeWire/PulseAudio. The
shared backend must meet the 10 ms calibrated error requirement before BASS is
removed from stable packaging in Plan 04.
