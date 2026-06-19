import build


def test_all_targets_collect_shared_runtime_packages():
    for target in build.BUILD_CONFIG.targets:
        assert "sounddevice" in target.collect_all
        assert "sudachipy" in target.collect_all
        assert "strange_uta_game.updater" in target.collect_submodules


def test_only_windows_collects_optional_winrt():
    assert "winrt" in build.BUILD_CONFIG.for_os("windows").optional_collect_all
    assert "winrt" not in build.BUILD_CONFIG.for_os("macos").optional_collect_all
    assert "winrt" not in build.BUILD_CONFIG.for_os("linux").optional_collect_all
