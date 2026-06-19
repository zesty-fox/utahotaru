from strange_uta_game.frontend.main_window import MainWindow


def test_main_window_uses_injected_audio_factory():
    sentinel = object()
    window = MainWindow.__new__(MainWindow)
    window._audio_engine_factory = lambda: sentinel

    assert window._make_audio_engine() is sentinel
