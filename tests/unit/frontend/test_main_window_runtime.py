from types import SimpleNamespace

from strange_uta_game.frontend.main_window import MainWindow
from strange_uta_game.runtime.capabilities import CapabilityRegistry
from strange_uta_game.runtime.context import RuntimeContext
from strange_uta_game.runtime.paths import AppPaths


def test_main_window_stores_injected_runtime_context(tmp_path):
    context = RuntimeContext(
        paths=AppPaths(tmp_path / "config", tmp_path / "data", tmp_path / "cache"),
        capabilities=CapabilityRegistry(),
    )
    holder = SimpleNamespace()

    MainWindow._set_runtime_context(holder, context)

    assert holder._runtime_context is context
