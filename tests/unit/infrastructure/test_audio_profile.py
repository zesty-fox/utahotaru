from strange_uta_game.backend.infrastructure.audio.profile import AudioProfile


def test_default_profile_is_platform_neutral():
    profile = AudioProfile.default()

    assert profile.block_frames == 1024
    assert profile.ring_seconds == 0.5
    assert profile.requested_latency_seconds == 0.1
    assert profile.thread_priority is None
