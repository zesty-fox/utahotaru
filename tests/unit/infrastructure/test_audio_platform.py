"""跨平台音频入口契约测试：BASS 可用性守卫与引擎选择。"""

import pytest

from strange_uta_game.backend.infrastructure import audio
from strange_uta_game.backend.infrastructure.audio import (
    IAudioEngine,
    bass_available,
    select_audio_engine,
)
from strange_uta_game.backend.infrastructure.audio.sounddevice_engine import (
    SoundDeviceEngine,
)


def test_audio_package_exposes_availability_signal():
    """包必须暴露 bass_available 布尔信号与 SoundDeviceEngine（跨平台默认引擎）。"""
    assert isinstance(bass_available, bool)
    assert SoundDeviceEngine is not None


def test_select_audio_engine_falls_back_when_bass_unavailable(monkeypatch):
    """BASS 不可用时，无论 HQ 开关都返回 SoundDeviceEngine。"""
    monkeypatch.setattr(audio, "bass_available", False)
    for hq in (True, False):
        engine = select_audio_engine(hq_enabled=hq)
        assert isinstance(engine, SoundDeviceEngine)
        assert isinstance(engine, IAudioEngine)


@pytest.mark.skipif(
    not bass_available,
    reason="仅在 BASS 可用（Windows）平台验证 BASS 引擎选型",
)
def test_select_audio_engine_uses_bass_when_available(monkeypatch):
    """BASS 可用时按 HQ 开关在 BassTsmEngine / BassEngine 间选择。"""
    from strange_uta_game.backend.infrastructure.audio import BassEngine, BassTsmEngine

    monkeypatch.setattr(audio, "bass_available", True)
    assert isinstance(select_audio_engine(hq_enabled=True), BassTsmEngine)
    assert isinstance(select_audio_engine(hq_enabled=False), BassEngine)


def test_create_keysound_player_falls_back_when_bass_unavailable(monkeypatch):
    """BASS 不可用时工厂返回 SoundDeviceKeySoundPlayer。"""
    from strange_uta_game.backend.infrastructure.audio import keysound_player
    from strange_uta_game.backend.infrastructure.audio.keysound_player import (
        SoundDeviceKeySoundPlayer,
        create_keysound_player,
    )

    monkeypatch.setattr(keysound_player, "bass_available", False)
    player = create_keysound_player()
    assert isinstance(player, SoundDeviceKeySoundPlayer)
