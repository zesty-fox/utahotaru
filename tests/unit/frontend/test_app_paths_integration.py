from __future__ import annotations

from strange_uta_game.backend.infrastructure.audio import tsm_cache, video_converter
from strange_uta_game.frontend.project_store import ProjectStore
from strange_uta_game.frontend.settings.app_settings import AppSettings
from strange_uta_game.runtime.paths import AppPaths


def _paths(tmp_path) -> AppPaths:
    return AppPaths(
        config=tmp_path / "config",
        data=tmp_path / "data",
        cache=tmp_path / "cache",
    ).ensure()


def test_app_settings_uses_injected_config_directory(tmp_path):
    paths = _paths(tmp_path)

    settings = AppSettings(app_paths=paths)
    settings.set("ui.language", "en_US")
    settings.save()

    assert (paths.config / "config.json").is_file()


def test_explicit_config_path_wins_over_injected_paths(tmp_path):
    paths = _paths(tmp_path)
    explicit_path = tmp_path / "portable" / "config.json"
    explicit_path.parent.mkdir()

    settings = AppSettings(str(explicit_path), app_paths=paths)
    settings.set("ui.language", "en_US")
    settings.save()

    assert explicit_path.is_file()
    assert not (paths.config / "config.json").exists()


def test_project_store_uses_injected_cache_directory(tmp_path, qapp):
    _ = qapp
    paths = _paths(tmp_path)

    store = ProjectStore(app_paths=paths)

    assert store.get_temp_path() == paths.cache / ".untitled.sug.temp"


def test_audio_caches_use_configured_root_but_keep_env_override(tmp_path, monkeypatch):
    paths = _paths(tmp_path)
    env_cache = tmp_path / "env-cache"
    try:
        tsm_cache.set_cache_root(paths.cache)
        video_converter.set_cache_root(paths.cache)
        monkeypatch.delenv("SUG_CACHE_DIR", raising=False)

        assert tsm_cache._get_cache_dir() == paths.cache
        assert video_converter._get_cache_dir() == paths.cache / "extracted"

        monkeypatch.setenv("SUG_CACHE_DIR", str(env_cache))
        assert tsm_cache._get_cache_dir() == env_cache
        assert video_converter._get_cache_dir() == env_cache / "extracted"
    finally:
        tsm_cache.set_cache_root(None)
        video_converter.set_cache_root(None)
