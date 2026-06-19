import json

from strange_uta_game.runtime.migration import migrate_legacy_data
from strange_uta_game.runtime.paths import AppPaths


def test_migration_copies_known_files_and_keeps_source(tmp_path):
    source = tmp_path / "legacy"
    source.mkdir()
    (source / "config.json").write_text(
        '{"ui": {"language": "ja_JP"}}', encoding="utf-8"
    )
    paths = AppPaths(tmp_path / "config", tmp_path / "data", tmp_path / "cache")

    result = migrate_legacy_data(paths, (source,))

    assert result.migrated == ("config.json",)
    assert (paths.config / "config.json").exists()
    assert (source / "config.json").exists()
    marker = json.loads(
        (paths.data / "migration-v1.json").read_text(encoding="utf-8")
    )
    assert marker["version"] == 1


def test_migration_is_idempotent_and_never_overwrites_target(tmp_path):
    source = tmp_path / "legacy"
    source.mkdir()
    (source / "config.json").write_text('{"source": true}', encoding="utf-8")
    paths = AppPaths(tmp_path / "config", tmp_path / "data", tmp_path / "cache")
    paths.ensure()
    (paths.config / "config.json").write_text('{"target": true}', encoding="utf-8")

    first = migrate_legacy_data(paths, (source,))
    second = migrate_legacy_data(paths, (source,))

    assert not first.migrated
    assert second.already_complete
    assert '"target": true' in (paths.config / "config.json").read_text(
        encoding="utf-8"
    )
