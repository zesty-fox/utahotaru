from strange_uta_game.runtime.paths import AppPaths, build_app_paths, legacy_roots


def test_build_app_paths_keeps_data_config_and_cache_separate(tmp_path):
    values = {
        "config": tmp_path / "config",
        "data": tmp_path / "data",
        "cache": tmp_path / "cache",
    }
    paths = build_app_paths(lambda key: values[key])
    assert paths == AppPaths(**values)


def test_legacy_roots_preserves_redirect_precedence(tmp_path):
    program = tmp_path / "program"
    redirected = tmp_path / "redirected"
    program.mkdir()
    redirected.mkdir()
    (program / ".config_redirect").write_text(str(redirected), encoding="utf-8")
    assert legacy_roots(program, tmp_path / "cwd")[0] == redirected
