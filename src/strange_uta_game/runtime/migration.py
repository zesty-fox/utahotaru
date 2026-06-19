"""Idempotent migration from legacy portable data locations."""

from __future__ import annotations

import json
import os
import shutil
from dataclasses import dataclass
from pathlib import Path

from .paths import AppPaths

CONFIG_FILES = (
    "config.json",
    "dictionary.json",
    "singers.json",
    "network_dictionary.json",
)
_MIGRATION_VERSION = 1
_MARKER_NAME = f"migration-v{_MIGRATION_VERSION}.json"


@dataclass(frozen=True)
class MigrationResult:
    """Outcome of one legacy-data migration attempt."""

    migrated: tuple[str, ...]
    source: str = ""
    already_complete: bool = False


def _atomic_copy(source: Path, target: Path) -> None:
    target.parent.mkdir(parents=True, exist_ok=True)
    temporary = target.with_suffix(target.suffix + ".migrating")
    try:
        shutil.copy2(source, temporary)
        os.replace(temporary, target)
    finally:
        temporary.unlink(missing_ok=True)


def _write_marker(marker: Path, payload: dict[str, object]) -> None:
    temporary = marker.with_suffix(marker.suffix + ".migrating")
    try:
        temporary.write_text(
            json.dumps(payload, ensure_ascii=False, sort_keys=True, indent=2) + "\n",
            encoding="utf-8",
        )
        os.replace(temporary, marker)
    finally:
        temporary.unlink(missing_ok=True)


def migrate_legacy_data(
    paths: AppPaths,
    roots: tuple[Path, ...],
) -> MigrationResult:
    """Copy legacy standalone files without overwriting canonical data."""

    paths.ensure()
    marker = paths.data / _MARKER_NAME
    if marker.is_file():
        return MigrationResult((), already_complete=True)

    source = next(
        (root for root in roots if any((root / name).is_file() for name in CONFIG_FILES)),
        None,
    )
    migrated: list[str] = []
    if source is not None:
        backup = paths.data / f"migration-backup-v{_MIGRATION_VERSION}"
        for name in CONFIG_FILES:
            source_file = source / name
            target_file = paths.config / name
            if not source_file.is_file() or target_file.exists():
                continue
            backup_file = backup / name
            if not backup_file.exists():
                _atomic_copy(source_file, backup_file)
            _atomic_copy(source_file, target_file)
            migrated.append(name)

    source_text = str(source) if source is not None else ""
    _write_marker(
        marker,
        {
            "version": _MIGRATION_VERSION,
            "source": source_text,
            "migrated": migrated,
        },
    )
    return MigrationResult(tuple(migrated), source=source_text)
