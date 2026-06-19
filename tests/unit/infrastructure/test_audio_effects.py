import numpy as np

from strange_uta_game.backend.infrastructure.audio.effects import EffectMixer


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
