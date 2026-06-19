from pathlib import Path


RUBY_ENTRYPOINTS = (
    Path("src/strange_uta_game/frontend/home/home_interface.py"),
    Path("src/strange_uta_game/frontend/editor/fulltext_interface.py"),
    Path("src/strange_uta_game/frontend/editor/timing_interface.py"),
)


def test_automatic_ruby_entrypoints_do_not_gate_on_winrt():
    for path in RUBY_ENTRYPOINTS:
        source = path.read_text(encoding="utf-8")
        assert "ensure_winrt_japanese" not in source
        assert "winrt_japanese_status" not in source
