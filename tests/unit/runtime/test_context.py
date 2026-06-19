from strange_uta_game.runtime.context import RuntimeContext, build_runtime_context
from strange_uta_game.runtime.capabilities import Capability
from strange_uta_game.runtime.paths import AppPaths


def test_build_runtime_context_runs_migration_once(tmp_path, monkeypatch):
    called = []
    paths = AppPaths(tmp_path / "config", tmp_path / "data", tmp_path / "cache")
    monkeypatch.setattr(
        "strange_uta_game.runtime.context.migrate_legacy_data",
        lambda app_paths, roots: called.append((app_paths, roots)),
    )

    context = build_runtime_context(
        program_dir=tmp_path,
        cwd=tmp_path,
        app_paths=paths,
    )

    assert isinstance(context, RuntimeContext)
    assert context.paths == paths
    assert len(called) == 1
    assert paths.config.is_dir()
    assert paths.data.is_dir()
    assert paths.cache.is_dir()


def test_runtime_context_reports_optional_winrt_capability(tmp_path, monkeypatch):
    paths = AppPaths(tmp_path / "config", tmp_path / "data", tmp_path / "cache")
    monkeypatch.setattr(
        "strange_uta_game.runtime.context.winrt_japanese_status",
        lambda: (True, "ok"),
    )

    context = build_runtime_context(tmp_path, tmp_path, app_paths=paths)

    status = context.capabilities.status(Capability.RUBY_WINRT)
    assert status.available
    assert status.provider == "winrt"
